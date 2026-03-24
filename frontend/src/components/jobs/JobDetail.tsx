"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { jobsApi, candidatesApi, searchApi, JobProfile, Candidate, MatchResult } from "@/lib/api";

// ── Status config ────────────────────────────────────────────────────────────

const CANDIDATE_STATUS: Record<string, { label: string; color: string }> = {
    new:        { label: "Nuevo",           color: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300" },
    screening:  { label: "Preseleccionado", color: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" },
    interview:  { label: "En entrevista",   color: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
    offer:      { label: "Oferta enviada",  color: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" },
    hired:      { label: "Contratado",      color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
    rejected:   { label: "Rechazado",       color: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" },
};

const STATUS_OPTIONS = [
    { value: "new",       label: "Nuevo" },
    { value: "screening", label: "Preseleccionado" },
    { value: "interview", label: "En entrevista" },
    { value: "offer",     label: "Oferta enviada" },
    { value: "hired",     label: "Contratado" },
    { value: "rejected",  label: "Rechazado" },
];

function statusMeta(s: string) {
    return CANDIDATE_STATUS[s] ?? CANDIDATE_STATUS["new"];
}

// ── Recommendation config ────────────────────────────────────────────────────

const REC_DOT: Record<string, string> = {
    "Altamente recomendado": "bg-emerald-500",
    "Buena opción":          "bg-blue-500",
    "Considerar":            "bg-amber-500",
    "No recomendado":        "bg-slate-400",
};

const REC_TEXT: Record<string, string> = {
    "Altamente recomendado": "text-emerald-600 dark:text-emerald-400",
    "Buena opción":          "text-blue-600 dark:text-blue-400",
    "Considerar":            "text-amber-600 dark:text-amber-400",
    "No recomendado":        "text-slate-500 dark:text-slate-400",
};

// ── Ranking section ──────────────────────────────────────────────────────────

type SortCol = "overall_score" | "skills_score" | "experience_score" | "education_score";

const COL_LABELS: Record<SortCol, string> = {
    overall_score:    "Total",
    skills_score:     "Skills",
    experience_score: "Exp.",
    education_score:  "Edu.",
};

function ScoreCell({ value, highlight }: { value: number; highlight?: boolean }) {
    const v = Math.round(value);
    const color = v >= 75 ? "text-emerald-600 dark:text-emerald-400"
        : v >= 55 ? "text-blue-600 dark:text-blue-400"
        : v >= 35 ? "text-amber-600 dark:text-amber-400"
        : "text-slate-400";
    return (
        <span className={`font-black text-lg tabular-nums ${color} ${highlight ? "underline decoration-dotted underline-offset-2" : ""}`}>
            {v}
        </span>
    );
}

function RankingSection({
    scores,
    loading,
    candidateCount,
    onRunMatch,
}: {
    scores: MatchResult[];
    loading: boolean;
    candidateCount: number;
    onRunMatch: () => void;
}) {
    const [sortBy, setSortBy] = useState<SortCol>("overall_score");
    const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

    function toggleSort(col: SortCol) {
        if (sortBy === col) setSortDir(d => d === "desc" ? "asc" : "desc");
        else { setSortBy(col); setSortDir("desc"); }
    }

    const sorted = [...scores].sort((a, b) => {
        const diff = (a[sortBy] ?? 0) - (b[sortBy] ?? 0);
        return sortDir === "desc" ? -diff : diff;
    });

    // timestamp of most recent score
    const lastRun = scores
        .map(s => s.scored_at)
        .filter(Boolean)
        .sort()
        .at(-1);

    const lastRunLabel = lastRun
        ? new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(lastRun))
        : null;

    return (
        <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <span className="material-symbols-outlined text-primary text-[22px]">psychology</span>
                    <div>
                        <p className="font-bold text-slate-900 dark:text-white">Ranking IA</p>
                        {lastRunLabel && !loading && (
                            <p className="text-xs text-slate-400">Actualizado: {lastRunLabel}</p>
                        )}
                    </div>
                </div>
                <button
                    onClick={onRunMatch}
                    disabled={candidateCount === 0 || loading}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <span className={`material-symbols-outlined text-[18px] ${loading ? "animate-spin" : ""}`}>
                        {loading ? "sync" : "psychology"}
                    </span>
                    {loading ? "Analizando..." : scores.length > 0 ? "Re-analizar" : "Analizar con IA"}
                </button>
            </div>

            {/* Body */}
            {loading ? (
                <div className="py-12 flex flex-col items-center gap-4 text-slate-500">
                    <span className="material-symbols-outlined text-[40px] text-primary animate-spin">sync</span>
                    <p className="text-sm">Evaluando {candidateCount} candidato{candidateCount !== 1 ? "s" : ""} con IA...</p>
                </div>
            ) : scores.length === 0 ? (
                <div className="py-12 text-center">
                    <span className="material-symbols-outlined text-[48px] text-slate-300 dark:text-slate-600 block mb-3">leaderboard</span>
                    <p className="text-slate-500 text-sm">
                        {candidateCount === 0
                            ? "Importa CVs primero para poder analizar."
                            : "Usa \"Analizar con IA\" para generar el ranking de compatibilidad."}
                    </p>
                </div>
            ) : (
                <div>
                    {/* Column headers / sort controls */}
                    <div className="grid grid-cols-[2rem_1fr_repeat(4,5rem)] px-5 py-2 border-b border-slate-100 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/80">
                        <span />
                        <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Candidato</span>
                        {(Object.keys(COL_LABELS) as SortCol[]).map(col => (
                            <button
                                key={col}
                                onClick={() => toggleSort(col)}
                                className={`flex items-center justify-center gap-0.5 text-[11px] font-bold uppercase tracking-wider transition-colors ${
                                    sortBy === col
                                        ? "text-primary"
                                        : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                                }`}
                            >
                                {COL_LABELS[col]}
                                {sortBy === col && (
                                    <span className="material-symbols-outlined text-[14px]">
                                        {sortDir === "desc" ? "arrow_downward" : "arrow_upward"}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Rows */}
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                        {sorted.map((s, i) => {
                            const initials = s.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
                            const dotColor = REC_DOT[s.recommendation] ?? "bg-slate-400";
                            const recText = REC_TEXT[s.recommendation] ?? "text-slate-500";
                            return (
                                <div key={s.candidate_id} className="grid grid-cols-[2rem_1fr_repeat(4,5rem)] items-center px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors">
                                    {/* Rank */}
                                    <span className="text-xs font-bold text-slate-400">#{i + 1}</span>

                                    {/* Name + rec */}
                                    <div className="flex items-center gap-2 min-w-0">
                                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                                            {initials}
                                        </div>
                                        <div className="min-w-0">
                                            <Link
                                                href={`/candidates/${s.candidate_id}`}
                                                className="text-sm font-semibold text-slate-900 dark:text-white hover:text-primary transition-colors truncate block"
                                            >
                                                {s.full_name}
                                            </Link>
                                            <span className={`flex items-center gap-1 text-[11px] font-medium ${recText}`}>
                                                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
                                                {s.recommendation}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Score columns */}
                                    <div className="flex justify-center">
                                        <ScoreCell value={s.overall_score} highlight={sortBy === "overall_score"} />
                                    </div>
                                    <div className="flex justify-center">
                                        <ScoreCell value={s.skills_score} highlight={sortBy === "skills_score"} />
                                    </div>
                                    <div className="flex justify-center">
                                        <ScoreCell value={s.experience_score} highlight={sortBy === "experience_score"} />
                                    </div>
                                    <div className="flex justify-center">
                                        <ScoreCell value={s.education_score} highlight={sortBy === "education_score"} />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
}


// ── Main Component ───────────────────────────────────────────────────────────

interface Props { jobId: string; }

const JobDetail: React.FC<Props> = ({ jobId }) => {
    const router = useRouter();
    const { user } = useAuth();

    const [job, setJob] = useState<JobProfile | null>(null);
    const [candidates, setCandidates] = useState<Candidate[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Persisted AI scores
    const [scores, setScores] = useState<MatchResult[]>([]);
    const [matchLoading, setMatchLoading] = useState(false);

    // Per-candidate delete confirm
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    // Job delete confirm
    const [showDeleteJobConfirm, setShowDeleteJobConfirm] = useState(false);
    const [deletingJob, setDeletingJob] = useState(false);

    // Status update tracking
    const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);

    useEffect(() => {
        loadAll();
    }, [jobId]);

    async function loadAll() {
        setLoading(true);
        setError(null);
        try {
            const [jobRes, candRes, scoresRes] = await Promise.all([
                jobsApi.get(jobId),
                candidatesApi.list(1, 100, jobId),
                jobsApi.getScores(jobId).catch(() => null),
            ]);
            setJob(jobRes.data);
            setCandidates(candRes.data.items || []);
            if (scoresRes?.data?.scores) setScores(scoresRes.data.scores);
        } catch (e: any) {
            setError("No se pudo cargar la convocatoria");
        } finally {
            setLoading(false);
        }
    }

    async function runMatch() {
        setMatchLoading(true);
        try {
            const res = await searchApi.match(jobId, 20);
            setScores(res.data.matches || []);
        } catch {
            // keep existing scores
        } finally {
            setMatchLoading(false);
        }
    }

    async function handleStatusChange(candidateId: string, newStatus: string) {
        setUpdatingStatusId(candidateId);
        try {
            await candidatesApi.updateStatus(candidateId, newStatus);
            setCandidates(prev => prev.map(c => c.id === candidateId ? { ...c, status: newStatus } : c));
        } finally {
            setUpdatingStatusId(null);
        }
    }

    async function handleDeleteCandidate(candidateId: string) {
        setDeleteError(null);
        try {
            await candidatesApi.delete(candidateId);
            setCandidates(prev => prev.filter(c => c.id !== candidateId));
            setScores(prev => prev.filter(s => s.candidate_id !== candidateId));
            setDeletingId(null);
            setJob(prev => prev ? { ...prev, candidate_count: (prev.candidate_count ?? 1) - 1 } : prev);
        } catch (e: any) {
            const msg = e.response?.data?.detail || "Error al eliminar";
            setDeleteError(msg);
            setDeletingId(null);
        }
    }

    async function handleDeleteJob() {
        setDeletingJob(true);
        try {
            await jobsApi.delete(jobId);
            router.push("/jobs");
        } catch {
            setDeletingJob(false);
            setShowDeleteJobConfirm(false);
        }
    }

    async function handleCloseJob() {
        const newStatus = job?.status === "active" ? "closed" : "active";
        try {
            await jobsApi.updateStatus(jobId, newStatus);
            setJob(prev => prev ? { ...prev, status: newStatus } : prev);
        } catch {}
    }

    // ── Loading / Error ──────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="flex items-center justify-center py-20">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
            </div>
        );
    }

    if (error || !job) {
        return (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
                <span className="material-symbols-outlined text-[48px] text-slate-400">error</span>
                <p className="text-slate-500">{error || "Convocatoria no encontrada"}</p>
                <Link href="/jobs" className="text-primary hover:underline text-sm">← Volver a Vacantes</Link>
            </div>
        );
    }

    const isAdmin = user?.role === "admin";

    // ── Render ───────────────────────────────────────────────────────────────

    return (
        <div className="space-y-6 max-w-5xl">

            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-slate-500">
                <Link href="/jobs" className="hover:text-primary transition-colors flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                    Perfiles de Puesto
                </Link>
                <span>/</span>
                <span className="text-slate-700 dark:text-slate-200 font-medium truncate">{job.title}</span>
            </div>

            {/* ── Header card ── */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl p-6">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    {/* Title + meta */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 flex-wrap mb-1">
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{job.title}</h1>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                                job.status === "active"
                                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                                    : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
                            }`}>
                                {job.status === "active" ? "Activo" : job.status === "closed" ? "Cerrado" : job.status}
                            </span>
                        </div>
                        {job.department && <p className="text-slate-500 text-sm">{job.department}</p>}

                        {/* Meta chips */}
                        <div className="flex flex-wrap gap-2 mt-3">
                            {job.seniority_level && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-300 text-xs font-medium border border-indigo-100 dark:border-indigo-800">
                                    <span className="material-symbols-outlined text-[13px]">grade</span>
                                    {job.seniority_level}
                                </span>
                            )}
                            {job.work_modality && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-teal-50 dark:bg-teal-900/20 text-teal-600 dark:text-teal-300 text-xs font-medium border border-teal-100 dark:border-teal-800">
                                    <span className="material-symbols-outlined text-[13px]">location_on</span>
                                    {job.work_modality}
                                </span>
                            )}
                            {job.industry && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300 text-xs font-medium border border-amber-100 dark:border-amber-800">
                                    <span className="material-symbols-outlined text-[13px]">business</span>
                                    {job.industry}
                                </span>
                            )}
                            {job.min_experience_years > 0 && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300 text-xs font-medium border border-slate-200 dark:border-slate-600">
                                    <span className="material-symbols-outlined text-[13px]">work_history</span>
                                    {job.min_experience_years}+ años
                                </span>
                            )}
                            {job.education_level && (
                                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-50 dark:bg-slate-700/50 text-slate-600 dark:text-slate-300 text-xs font-medium border border-slate-200 dark:border-slate-600">
                                    <span className="material-symbols-outlined text-[13px]">school</span>
                                    {job.education_level}
                                </span>
                            )}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2 flex-shrink-0">
                        <button
                            onClick={() => router.push(`/data?job_id=${job.id}`)}
                            className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined text-[18px]">upload_file</span>
                            Importar CVs
                        </button>
                        <MoreMenu status={job.status} onClose={handleCloseJob} onDelete={() => setShowDeleteJobConfirm(true)} />
                    </div>
                </div>

                {/* CV count bar */}
                <div className="mt-5 flex items-center gap-2 py-3 px-4 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800">
                    <span className="material-symbols-outlined text-[20px] text-indigo-500">folder_open</span>
                    <span className="text-xl font-black text-indigo-600 dark:text-indigo-300">{candidates.length}</span>
                    <span className="text-sm text-indigo-500 dark:text-indigo-400">
                        candidato{candidates.length !== 1 ? "s" : ""} en esta convocatoria
                    </span>
                </div>
            </div>

            {/* ── Job details ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {(job.description || (job.key_objectives?.length ?? 0) > 0 || (job.responsibilities?.length ?? 0) > 0) && (
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 space-y-4">
                        {job.description && (
                            <div>
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Descripción</h3>
                                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{job.description}</p>
                            </div>
                        )}
                        {(job.responsibilities?.length ?? 0) > 0 && (
                            <div>
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Responsabilidades</h3>
                                <ul className="space-y-1">
                                    {job.responsibilities!.map((r, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                                            <span className="text-primary mt-0.5 flex-shrink-0">·</span>{r}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {(job.key_objectives?.length ?? 0) > 0 && (
                            <div>
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Objetivos clave</h3>
                                <ul className="space-y-1">
                                    {job.key_objectives!.map((o, i) => (
                                        <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                                            <span className="text-emerald-500 mt-0.5 flex-shrink-0">✓</span>{o}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}

                {((job.required_skills?.length ?? 0) > 0 || (job.preferred_skills?.length ?? 0) > 0) && (
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 space-y-4">
                        {(job.required_skills?.length ?? 0) > 0 && (
                            <div>
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Habilidades requeridas</h3>
                                <div className="flex flex-wrap gap-1.5">
                                    {job.required_skills.map((s, i) => (
                                        <span key={i} className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">{s}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                        {(job.preferred_skills?.length ?? 0) > 0 && (
                            <div>
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Habilidades deseables</h3>
                                <div className="flex flex-wrap gap-1.5">
                                    {job.preferred_skills.map((s, i) => (
                                        <span key={i} className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium">{s}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* ── AI Ranking (persistent) ── */}
            <RankingSection
                scores={scores}
                loading={matchLoading}
                candidateCount={candidates.length}
                onRunMatch={runMatch}
            />

            {/* ── Candidates list ── */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-slate-400 text-[20px]">group</span>
                        <h2 className="font-bold text-slate-900 dark:text-white">Candidatos</h2>
                        <span className="ml-1 px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-xs font-semibold text-slate-500">{candidates.length}</span>
                    </div>
                    <button
                        onClick={() => router.push(`/data?job_id=${job.id}`)}
                        className="flex items-center gap-1.5 text-sm text-primary hover:text-blue-600 font-medium transition-colors"
                    >
                        <span className="material-symbols-outlined text-[17px]">add</span>
                        Importar CVs
                    </button>
                </div>

                {deleteError && (
                    <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400">
                        {deleteError}
                    </div>
                )}

                {candidates.length === 0 ? (
                    <div className="py-14 text-center">
                        <span className="material-symbols-outlined text-[48px] text-slate-300 dark:text-slate-600 block mb-3">upload_file</span>
                        <p className="text-slate-500 mb-4">Aún no hay CVs en esta convocatoria</p>
                        <button
                            onClick={() => router.push(`/data?job_id=${job.id}`)}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600"
                        >
                            <span className="material-symbols-outlined text-[18px]">upload_file</span>
                            Importar CVs
                        </button>
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                        {candidates.map(candidate => (
                            <CandidateRow
                                key={candidate.id}
                                candidate={candidate}
                                isDeleting={deletingId === candidate.id}
                                isUpdating={updatingStatusId === candidate.id}
                                isAdmin={isAdmin}
                                onStatusChange={(s) => handleStatusChange(candidate.id, s)}
                                onDeleteRequest={() => { setDeletingId(candidate.id); setDeleteError(null); }}
                                onDeleteConfirm={() => handleDeleteCandidate(candidate.id)}
                                onDeleteCancel={() => setDeletingId(null)}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* ── Delete job confirmation modal ── */}
            {showDeleteJobConfirm && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-sm p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center flex-shrink-0">
                                <span className="material-symbols-outlined text-red-500">delete_forever</span>
                            </div>
                            <div>
                                <h3 className="font-bold text-slate-900 dark:text-white">Eliminar convocatoria</h3>
                                <p className="text-xs text-slate-500">Esta acción no se puede deshacer</p>
                            </div>
                        </div>
                        <p className="text-sm text-slate-600 dark:text-slate-300 mb-5">
                            Se eliminará <strong>"{job.title}"</strong> y todos sus CVs asociados.
                        </p>
                        <div className="flex gap-3">
                            <button
                                onClick={() => setShowDeleteJobConfirm(false)}
                                className="flex-1 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleDeleteJob}
                                disabled={deletingJob}
                                className="flex-1 px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors disabled:opacity-60"
                            >
                                {deletingJob ? "Eliminando..." : "Eliminar"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// ── Candidate Row ────────────────────────────────────────────────────────────

interface CandidateRowProps {
    candidate: Candidate;
    isDeleting: boolean;
    isUpdating: boolean;
    isAdmin: boolean;
    onStatusChange: (s: string) => void;
    onDeleteRequest: () => void;
    onDeleteConfirm: () => void;
    onDeleteCancel: () => void;
}

function CandidateRow({ candidate, isDeleting, isUpdating, isAdmin, onStatusChange, onDeleteRequest, onDeleteConfirm, onDeleteCancel }: CandidateRowProps) {
    const initials = candidate.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
    const meta = statusMeta(candidate.status);

    return (
        <div className={`px-6 py-4 flex items-center gap-4 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors ${isDeleting ? "bg-red-50 dark:bg-red-900/10" : ""}`}>
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                {initials}
            </div>

            <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900 dark:text-white text-sm truncate">{candidate.full_name}</p>
                {candidate.skills.length > 0 && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                        {candidate.skills.slice(0, 4).join(" · ")}{candidate.skills.length > 4 ? ` +${candidate.skills.length - 4}` : ""}
                    </p>
                )}
            </div>

            <div className="flex-shrink-0">
                {isUpdating ? (
                    <span className="text-xs text-slate-400 animate-pulse">Actualizando...</span>
                ) : (
                    <select
                        value={candidate.status}
                        onChange={e => onStatusChange(e.target.value)}
                        className={`text-xs font-semibold px-2.5 py-1 rounded-full border-0 cursor-pointer focus:ring-2 focus:ring-primary outline-none ${meta.color}`}
                    >
                        {STATUS_OPTIONS.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                )}
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
                {isDeleting ? (
                    <>
                        <span className="text-xs text-red-600 dark:text-red-400 font-medium">¿Eliminar?</span>
                        <button onClick={onDeleteConfirm} className="px-2.5 py-1 rounded-lg bg-red-500 hover:bg-red-600 text-white text-xs font-semibold transition-colors">Sí</button>
                        <button onClick={onDeleteCancel} className="px-2.5 py-1 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">No</button>
                    </>
                ) : (
                    <>
                        <Link
                            href={`/candidates/${candidate.id}`}
                            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-primary transition-colors"
                            title="Ver perfil"
                        >
                            <span className="material-symbols-outlined text-[18px]">open_in_new</span>
                        </Link>
                        {isAdmin && (
                            <button
                                onClick={onDeleteRequest}
                                className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-slate-400 hover:text-red-500 transition-colors"
                                title="Eliminar candidato"
                            >
                                <span className="material-symbols-outlined text-[18px]">delete</span>
                            </button>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

// ── More Menu ────────────────────────────────────────────────────────────────

function MoreMenu({ status, onClose, onDelete }: { status: string; onClose: () => void; onDelete: () => void }) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        }
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen(o => !o)}
                className="flex items-center gap-1 px-3.5 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
                <span className="material-symbols-outlined text-[18px]">more_vert</span>
            </button>
            {open && (
                <div className="absolute right-0 top-full mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-20 min-w-[180px] overflow-hidden">
                    <button
                        onClick={() => { onClose(); setOpen(false); }}
                        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">{status === "active" ? "lock" : "lock_open"}</span>
                        {status === "active" ? "Cerrar vacante" : "Reabrir vacante"}
                    </button>
                    <button
                        onClick={() => { onDelete(); setOpen(false); }}
                        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                        Eliminar vacante
                    </button>
                </div>
            )}
        </div>
    );
}

export default JobDetail;
