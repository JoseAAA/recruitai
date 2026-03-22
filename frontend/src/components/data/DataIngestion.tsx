"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import FileUploadZone from "./FileUploadZone";
import { candidatesApi, jobsApi, JobProfile, UploadResponse } from "@/lib/api";

interface DataSource {
    id: string;
    name: string;
    type: "manual" | "folder_watch";
    description: string;
    status: "ready" | "active" | "error";
    icon: string;
    color: string;
}

interface ActivityItem {
    id: string;
    source: string;
    status: "processing" | "completed" | "error";
    volume: string;
    time: string;
}

const DataIngestion: React.FC = () => {
    const searchParams = useSearchParams();
    // Simplified data sources - no complex OAuth required
    const [sources] = useState<DataSource[]>([
        {
            id: "manual",
            name: "Subida Manual",
            type: "manual",
            description: "Arrastra y suelta archivos PDF o DOCX",
            status: "ready",
            icon: "upload_file",
            color: "indigo",
        },
        {
            id: "folder",
            name: "Carpeta Local",
            type: "folder_watch",
            description: "Próximamente: monitoreo de carpeta automático",
            status: "ready",
            icon: "folder_open",
            color: "emerald",
        },
    ]);

    const [activities, setActivities] = useState<ActivityItem[]>([]);
    const [showUploadZone, setShowUploadZone] = useState(true); // Show by default
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [currentFile, setCurrentFile] = useState("");
    const [uploadResults, setUploadResults] = useState<UploadResponse[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [jobs, setJobs] = useState<JobProfile[]>([]);
    const [selectedJobId, setSelectedJobId] = useState<string>("");

    useEffect(() => {
        jobsApi.list().then(res => {
            const activeJobs = res.data.items.filter(j => j.status === "active");
            setJobs(activeJobs);
            // Pre-select job if job_id is in URL (e.g. coming from job card)
            const urlJobId = searchParams?.get("job_id");
            if (urlJobId) setSelectedJobId(urlJobId);
        }).catch(() => {});
    }, [searchParams]);

    const handleFilesSelected = async (files: File[]) => {
        if (files.length === 0) return;

        setIsUploading(true);
        setUploadProgress(0);
        setError(null);
        setUploadResults([]);

        try {
            const results = await candidatesApi.uploadMultiple(
                files,
                selectedJobId || undefined,
                (current, total, filename) => {
                    setCurrentFile(filename);
                    setUploadProgress(Math.round((current / total) * 100));
                }
            );

            setUploadResults(results);

            const successCount = results.filter(r => r.status !== "error").length;
            const errorCount = results.filter(r => r.status === "error").length;

            // Add to activity
            setActivities((prev) => [
                {
                    id: Date.now().toString(),
                    source: `Carga Manual #${Math.floor(Math.random() * 1000)}`,
                    status: errorCount > 0 ? (successCount > 0 ? "completed" : "error") : "completed",
                    volume: `${successCount} procesados${errorCount > 0 ? `, ${errorCount} errores` : ""}`,
                    time: "Justo ahora",
                },
                ...prev,
            ]);

        } catch (err: any) {
            setError(err.message || "Error al subir archivos");
        } finally {
            setIsUploading(false);
            setUploadProgress(100);
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "ready":
                return (
                    <span className="flex items-center gap-1.5 text-sm text-slate-400">
                        <span className="material-symbols-outlined text-[16px]">check_circle</span>
                        Sistema listo para recibir archivos
                    </span>
                );
            case "connected":
                return (
                    <span className="flex items-center gap-1.5 text-sm text-emerald-400">
                        <span className="material-symbols-outlined text-[16px]">check_circle</span>
                        Sistema conectado
                    </span>
                );
            case "syncing":
                return (
                    <span className="flex items-center gap-1.5 text-sm text-cyan-400">
                        <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                        Sincronizando...
                    </span>
                );
            case "error":
                return (
                    <span className="flex items-center gap-1.5 text-sm text-rose-400">
                        <span className="material-symbols-outlined text-[16px]">error</span>
                        Error de conexión
                    </span>
                );
            case "not_configured":
                return (
                    <span className="flex items-center gap-1.5 text-sm text-amber-400">
                        <span className="material-symbols-outlined text-[16px]">warning</span>
                        Requiere configuración
                    </span>
                );
            default:
                return null;
        }
    };

    const getColorClasses = (color: string) => {
        const colors: Record<string, { bg: string; border: string; icon: string }> = {
            slate: {
                bg: "bg-slate-500/10",
                border: "border-slate-500/30",
                icon: "text-slate-400",
            },
            blue: {
                bg: "bg-blue-500/10",
                border: "border-blue-500/30",
                icon: "text-blue-400",
            },
            cyan: {
                bg: "bg-cyan-500/10",
                border: "border-cyan-500/30",
                icon: "text-cyan-400",
            },
        };
        return colors[color] || colors.slate;
    };

    const getActivityStatus = (status: string) => {
        switch (status) {
            case "processing":
                return (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        Procesando
                    </span>
                );
            case "completed":
                return (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        Finalizado
                    </span>
                );
            case "error":
                return (
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30">
                        Error
                    </span>
                );
            default:
                return null;
        }
    };

    return (
        <>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white">Centro de Ingesta de Datos</h1>
                    <p className="text-slate-400 text-sm mt-1">
                        Configure y gestione las fuentes de origen de los Currículums.
                    </p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setShowUploadZone(!showUploadZone)}
                        className={`flex items-center gap-2 px-4 py-2 font-medium rounded-lg transition-colors shadow-sm ${showUploadZone
                            ? "bg-indigo-600 text-white"
                            : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                            }`}
                    >
                        <span className="material-symbols-outlined text-[20px]">upload_file</span>
                        Subir CVs
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm">
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        Añadir Fuente
                    </button>
                </div>
            </div>

            {/* Upload Zone (collapsible) */}
            {showUploadZone && (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="font-bold text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-indigo-400">cloud_upload</span>
                            Subida Manual de CVs
                        </h2>
                        <button
                            onClick={() => setShowUploadZone(false)}
                            className="text-slate-400 hover:text-white transition-colors"
                        >
                            <span className="material-symbols-outlined">close</span>
                        </button>
                    </div>

                    {/* Job selector — scope CVs to a specific position */}
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-slate-300 mb-1">
                            Asociar CVs a puesto de trabajo
                        </label>
                        <select
                            value={selectedJobId}
                            onChange={e => setSelectedJobId(e.target.value)}
                            className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        >
                            <option value="">Sin asociar (general)</option>
                            {jobs.map(j => (
                                <option key={j.id} value={j.id}>
                                    {j.title}{j.department ? ` — ${j.department}` : ""}
                                    {j.candidate_count != null ? ` (${j.candidate_count} CVs)` : ""}
                                </option>
                            ))}
                        </select>
                        {selectedJobId && (
                            <p className="mt-1 text-xs text-indigo-400">
                                Los CVs subidos se asociarán al puesto seleccionado y el matching solo buscará entre ellos.
                            </p>
                        )}
                    </div>

                    <FileUploadZone
                        onFilesSelected={handleFilesSelected}
                        isUploading={isUploading}
                        uploadProgress={uploadProgress}
                    />

                    {/* Upload Results */}
                    {uploadResults.length > 0 && (
                        <div className="mt-4 space-y-2">
                            <p className="text-sm font-medium text-slate-300">Resultados:</p>
                            <div className="max-h-40 overflow-y-auto space-y-2">
                                {uploadResults.map((result, i) => (
                                    <div
                                        key={i}
                                        className={`p-3 rounded-lg text-sm flex items-center justify-between ${result.status === "error"
                                            ? "bg-rose-500/10 border border-rose-500/30"
                                            : "bg-emerald-500/10 border border-emerald-500/30"
                                            }`}
                                    >
                                        <div className="flex items-center gap-2">
                                            <span
                                                className={`material-symbols-outlined text-[18px] ${result.status === "error" ? "text-rose-400" : "text-emerald-400"
                                                    }`}
                                            >
                                                {result.status === "error" ? "error" : "check_circle"}
                                            </span>
                                            <span className="text-white">{result.filename}</span>
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
                                ))}
                            </div>
                        </div>
                    )}

                    {error && (
                        <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400 text-sm">
                            {error}
                        </div>
                    )}
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
                            <h3 className="font-bold text-white flex items-center gap-2">
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
                            <span className="block text-2xl font-bold text-white">~3s</span>
                            <span className="text-slate-500">por CV</span>
                        </div>
                        <div className="text-center">
                            <span className="block text-2xl font-bold text-white">95%</span>
                            <span className="text-slate-500">precisión</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Data Sources Grid - Simple info cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {sources.map((source: DataSource) => {
                    const colorClasses = getColorClasses(source.color);
                    return (
                        <div
                            key={source.id}
                            className={`bg-slate-800/50 border ${colorClasses.border} rounded-xl p-5`}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={`p-2.5 rounded-lg ${colorClasses.bg}`}>
                                    <span className={`material-symbols-outlined text-[28px] ${colorClasses.icon}`}>
                                        {source.icon}
                                    </span>
                                </div>
                                <div>
                                    <h3 className="font-bold text-white">{source.name}</h3>
                                    <p className="text-sm text-slate-400">{source.description}</p>
                                </div>
                            </div>
                            <div>{getStatusBadge(source.status)}</div>
                        </div>
                    );
                })}
            </div>

            {/* Recent Activity */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-700">
                    <h2 className="text-lg font-bold text-white">Actividad Reciente</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-700">
                                <th className="text-left py-3 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    Fuente
                                </th>
                                <th className="text-left py-3 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    Estado
                                </th>
                                <th className="text-left py-3 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    Volumen
                                </th>
                                <th className="text-left py-3 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    Tiempo
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50">
                            {activities.map((activity) => (
                                <tr key={activity.id} className="hover:bg-slate-800/30 transition-colors">
                                    <td className="py-4 px-6 text-sm font-medium text-white">{activity.source}</td>
                                    <td className="py-4 px-6">{getActivityStatus(activity.status)}</td>
                                    <td className="py-4 px-6 text-sm text-slate-400">{activity.volume}</td>
                                    <td className="py-4 px-6 text-sm text-slate-500">{activity.time}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Help Section */}
            <div className="bg-slate-800/30 border border-slate-700 rounded-xl p-5">
                <h3 className="font-bold text-white mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-[20px] text-amber-400">lightbulb</span>
                    ¿Cómo funciona la asignación automática?
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                            1
                        </div>
                        <div>
                            <p className="font-medium text-slate-200">Sube CVs por puesto</p>
                            <p className="text-slate-400">Selecciona el puesto antes de subir para que el matching sea preciso y económico</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                            2
                        </div>
                        <div>
                            <p className="font-medium text-slate-200">Análisis con IA</p>
                            <p className="text-slate-400">Extraemos habilidades y experiencia</p>
                        </div>
                    </div>
                    <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold">
                            3
                        </div>
                        <div>
                            <p className="font-medium text-slate-200">Match Automático</p>
                            <p className="text-slate-400">Sugerimos candidatos por vacante</p>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default DataIngestion;
