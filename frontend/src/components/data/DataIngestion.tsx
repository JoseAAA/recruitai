"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import FileUploadZone from "./FileUploadZone";
import { candidatesApi, jobsApi, JobProfile, UploadResponse } from "@/lib/api";

const DataIngestion: React.FC = () => {
    const searchParams = useSearchParams();

    const [showUploadZone, setShowUploadZone] = useState(true); // Show by default
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [currentFile, setCurrentFile] = useState("");
    const [uploadResults, setUploadResults] = useState<UploadResponse[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [jobs, setJobs] = useState<JobProfile[]>([]);
    const [selectedJobId, setSelectedJobId] = useState<string>("");
    const [completedCount, setCompletedCount] = useState(0);
    const [totalFilesCount, setTotalFilesCount] = useState(0);
    const [estimatedRemaining, setEstimatedRemaining] = useState("");
    const [measuredAvgSecs, setMeasuredAvgSecs] = useState(0);
    const uploadStartRef = useRef<number>(0);

    // When the recruiter opens this page from a job-detail "Importar CVs"
    // button we keep the originating job_id so we can offer a one-click
    // return path after the upload finishes — instead of forcing them to
    // navigate back through the job list.
    const fromJobId = searchParams?.get("job_id") || "";
    const cameFromJobDetail = !!fromJobId;
    const fromJob = cameFromJobDetail ? jobs.find(j => j.id === fromJobId) : undefined;

    useEffect(() => {
        jobsApi.list().then(res => {
            const activeJobs = res.data.items.filter(j => j.status === "active");
            setJobs(activeJobs);
            if (fromJobId) setSelectedJobId(fromJobId);
        }).catch(() => {});
    }, [fromJobId]);

    const handleFilesSelected = async (files: File[]) => {
        if (files.length === 0) return;

        setIsUploading(true);
        setUploadProgress(0);
        setError(null);
        setUploadResults([]);
        setCompletedCount(0);
        setTotalFilesCount(files.length);
        setEstimatedRemaining("");
        uploadStartRef.current = Date.now();

        try {
            const results = await candidatesApi.uploadMultiple(
                files,
                selectedJobId || undefined,
                (current, total, filename) => {
                    setCurrentFile(filename);
                    setCompletedCount(current);
                    setUploadProgress(Math.round((current / total) * 100));
                    if (current > 0) {
                        const elapsed = (Date.now() - uploadStartRef.current) / 1000;
                        const secsPerFile = elapsed / current;           // wall-clock avg (concurrency included)
                        const remainingSecs = (total - current) * secsPerFile;
                        setMeasuredAvgSecs(Math.round(secsPerFile));
                        setEstimatedRemaining(
                            remainingSecs < 5 ? "" :
                            remainingSecs < 60 ? `~${Math.ceil(remainingSecs)}s` :
                            `~${Math.ceil(remainingSecs / 60)} min`
                        );
                    }
                }
            );

            setUploadResults(results);
        } catch (err: any) {
            setError(err.message || "Error al subir archivos");
        } finally {
            setIsUploading(false);
            setUploadProgress(100);
            setEstimatedRemaining("");
        }
    };

    return (
        <>
            {/* Back-to-job breadcrumb when launched from a job detail */}
            {cameFromJobDetail && (
                <div className="mb-1">
                    <Link
                        href={`/jobs/${fromJobId}`}
                        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-primary transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                        Volver al perfil del puesto
                        {fromJob ? <span className="font-medium text-slate-700 dark:text-slate-300">— {fromJob.title}</span> : null}
                    </Link>
                </div>
            )}

            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        {cameFromJobDetail ? "Importar CVs al puesto" : "Importar CVs"}
                    </h1>
                    <p className="text-slate-400 text-sm mt-1">
                        {cameFromJobDetail
                            ? "Los CVs subidos quedarán asociados al puesto seleccionado."
                            : "Sube CVs y asígnalos a una vacante. La IA los procesa al instante."}
                    </p>
                </div>
            </div>

            {/* Upload Zone (collapsible) */}
            {showUploadZone && (
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-indigo-400">cloud_upload</span>
                            Subida Manual de CVs
                        </h2>
                        <button
                            onClick={() => setShowUploadZone(false)}
                            className="text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors"
                        >
                            <span className="material-symbols-outlined">close</span>
                        </button>
                    </div>

                    {/* Job selector — required, every CV must belong to a vacancy */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                            Puesto de trabajo <span className="text-rose-500">*</span>
                        </label>
                        <select
                            value={selectedJobId}
                            onChange={e => setSelectedJobId(e.target.value)}
                            className={`w-full bg-white dark:bg-slate-700 border text-slate-900 dark:text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors ${
                                selectedJobId
                                    ? "border-slate-200 dark:border-slate-600"
                                    : "border-amber-300 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/10"
                            }`}
                        >
                            <option value="">— Selecciona un puesto —</option>
                            {jobs.map(j => (
                                <option key={j.id} value={j.id}>
                                    {j.title}{j.department ? ` — ${j.department}` : ""}
                                    {j.candidate_count != null ? ` (${j.candidate_count} CVs)` : ""}
                                </option>
                            ))}
                        </select>
                        {!selectedJobId ? (
                            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                                <span className="material-symbols-outlined text-[13px]">info</span>
                                Debes seleccionar un puesto antes de subir CVs. Cada CV debe pertenecer a una vacante.
                            </p>
                        ) : (
                            <p className="mt-1 flex items-center gap-1 text-xs text-indigo-500 dark:text-indigo-400">
                                <span className="material-symbols-outlined text-[13px]">check_circle</span>
                                Los CVs se asociarán a este puesto. El matching IA solo buscará entre ellos.
                            </p>
                        )}

                        {jobs.length === 0 && (
                            <div className="mt-2 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-500 flex items-center gap-2">
                                <span className="material-symbols-outlined text-[15px] text-slate-400">work_off</span>
                                No hay puestos activos. <Link href="/jobs/new" className="text-primary underline font-medium">Crea una vacante primero</Link>.
                            </div>
                        )}
                    </div>

                    {/* Block upload zone when no job selected */}
                    <div className={`transition-opacity ${selectedJobId ? "opacity-100" : "opacity-40 pointer-events-none select-none"}`}>
                        <FileUploadZone
                            onFilesSelected={handleFilesSelected}
                            isUploading={isUploading}
                            uploadProgress={uploadProgress}
                            currentFile={currentFile}
                            completedCount={completedCount}
                            totalFiles={totalFilesCount}
                            estimatedRemaining={estimatedRemaining}
                        />
                    </div>

                    {/* Upload Results */}
                    {uploadResults.length > 0 && (
                        <div className="mt-4 space-y-2">
                            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Resultados:</p>
                            <div className="max-h-40 overflow-y-auto space-y-2">
                                {uploadResults.map((result, i) => {
                                    const isSecurityBlock = result.status === "error" && result.message?.startsWith("ARCHIVO_RECHAZADO_SEGURIDAD:");
                                    const cleanMsg = isSecurityBlock
                                        ? result.message.replace("ARCHIVO_RECHAZADO_SEGURIDAD:", "").trim()
                                        : result.message;
                                    return (
                                        <div
                                            key={i}
                                            className={`p-3 rounded-lg text-sm ${
                                                isSecurityBlock
                                                    ? "bg-amber-500/10 border border-amber-500/30"
                                                    : result.status === "error"
                                                        ? "bg-rose-500/10 border border-rose-500/30"
                                                        : "bg-emerald-500/10 border border-emerald-500/30"
                                            }`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <span className={`material-symbols-outlined text-[18px] ${
                                                        isSecurityBlock ? "text-amber-400" : result.status === "error" ? "text-rose-400" : "text-emerald-400"
                                                    }`}>
                                                        {isSecurityBlock ? "shield" : result.status === "error" ? "error" : "check_circle"}
                                                    </span>
                                                    <span className="text-slate-900 dark:text-white">{result.filename}</span>
                                                    {result.extracted_name && (
                                                        <span className="text-slate-400">→ {result.extracted_name}</span>
                                                    )}
                                                </div>
                                                {result.skills_count > 0 && (
                                                    <span className="text-xs text-slate-400">
                                                        {result.skills_count} habilidades
                                                    </span>
                                                )}
                                            </div>
                                            {isSecurityBlock ? (
                                                <p className="mt-1.5 text-xs text-amber-700 dark:text-amber-300 pl-6">
                                                    {cleanMsg || "CV bloqueado por seguridad — contiene texto oculto. Pedile al candidato que lo reenvíe limpio."}
                                                </p>
                                            ) : result.status === "error" && result.message ? (
                                                <p className="mt-1.5 text-xs text-rose-700 dark:text-rose-300 pl-6">
                                                    {result.message}
                                                </p>
                                            ) : null}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}

                    {error && (() => {
                        const isSecErr = error.startsWith("ARCHIVO_RECHAZADO_SEGURIDAD:");
                        return (
                            <div className={`mt-4 p-3 rounded-lg text-sm flex items-start gap-2 ${isSecErr ? "bg-amber-500/10 border border-amber-500/30 text-amber-400" : "bg-rose-500/10 border border-rose-500/30 text-rose-400"}`}>
                                <span className="material-symbols-outlined text-[18px] shrink-0 mt-0.5">{isSecErr ? "shield" : "error"}</span>
                                <span>{isSecErr ? error.replace("ARCHIVO_RECHAZADO_SEGURIDAD:", "Archivo rechazado por seguridad:") : error}</span>
                            </div>
                        );
                    })()}
                </div>
            )}

            {/* AI Status Banner */}
            <div className="bg-gradient-to-r from-emerald-500/10 via-indigo-500/10 to-violet-500/10 border border-emerald-500/30 rounded-xl p-4">
                <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-emerald-500/20 rounded-lg">
                            <span className="material-symbols-outlined text-emerald-400 text-[28px]">psychology</span>
                        </div>
                        <div>
                            <h3 className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                Motor de IA Activo
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-400">
                                    Operativo
                                </span>
                            </h3>
                            <p className="text-sm text-slate-400">
                                Los CVs se procesan automáticamente al subirlos
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm">
                        <div className="text-center">
                            <span className="block text-2xl font-bold text-slate-900 dark:text-white">
                                {measuredAvgSecs > 0 ? `~${measuredAvgSecs}s` : "~20s"}
                            </span>
                            <span className="text-slate-500">por CV {measuredAvgSecs > 0 ? "(medido)" : "(CPU)"}</span>
                        </div>
                        <div className="text-center">
                            <span className="block text-2xl font-bold text-slate-900 dark:text-white">95%</span>
                            <span className="text-slate-500">precisión</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Quick return-to-job CTA after a successful upload, when launched from a job. */}
            {cameFromJobDetail && uploadResults.length > 0 && !isUploading && (
                <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-300 dark:border-emerald-700/40 rounded-xl p-5 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <span className="material-symbols-outlined text-emerald-500 text-[28px]">check_circle</span>
                        <div>
                            <h3 className="font-bold text-slate-900 dark:text-white">Subida finalizada</h3>
                            <p className="text-sm text-slate-500 dark:text-slate-400">
                                {uploadResults.filter(r => r.status !== "error").length} CV(s) procesados.
                                Continúa la revisión en el perfil del puesto.
                            </p>
                        </div>
                    </div>
                    <Link
                        href={`/jobs/${fromJobId}`}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 transition-colors shadow-sm"
                    >
                        <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                        Volver al perfil del puesto
                    </Link>
                </div>
            )}
        </>
    );
};

export default DataIngestion;
