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

// ── Match UI (reused from JobsList) ─────────────────────────────────────────

const RECOMMENDATION_META: Record<string, { label: string; color: string; bg: string; border: string; dot: string }> = {
    "Altamente recomendado": { label: "Altamente recomendado", color: "text-emerald-700 dark:text-emerald-300", bg: "bg-emerald-50 dark:bg-emerald-900/30", border: "border-emerald-200 dark:border-emerald-700", dot: "bg-emerald-500" },
    "Buena opción":          { label: "Buena opción",          color: "text-blue-700 dark:text-blue-300",       bg: "bg-blue-50 dark:bg-blue-900/30",       border: "border-blue-200 dark:border-blue-700",    dot: "bg-blue-500"   },
    "Considerar":            { label: "Considerar",            color: "text-amber-700 dark:text-amber-300",     bg: "bg-amber-50 dark:bg-amber-900/30",     border: "border-amber-200 dark:border-amber-700",  dot: "bg-amber-500"  },
    "No recomendado":        { label: "No recomendado",        color: "text-slate-500 dark:text-slate-400",     bg: "bg-slate-50 dark:bg-slate-800/50",     border: "border-slate-200 dark:border-slate-700",  dot: "bg-slate-400"  },
};
function recMeta(r: string) { return RECOMMENDATION_META[r] ?? RECOMMENDATION_META["Considerar"]; }

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div>
            <div className="flex justify-between items-center mb-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
                <span className="text-xs font-bold text-slate-700 dark:text-slate-300">{Math.round(value)}%</span>
            </div>
            <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${value}%` }} />
            </div>
        </div>
    );
}

function CandidateMatchCard({ match, index }: { match: MatchResult; index: number }) {
    const meta = recMeta(match.recommendation);
    const score = Math.round(match.overall_score);
    const initials = match.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
    const scoreColor = score >= 75 ? "text-emerald-600" : score >= 55 ? "text-blue-600" : score >= 35 ? "text-amber-600" : "text-slate-500";
    return (
        <div className={`rounded-xl border ${meta.border} ${meta.bg} p-5`}>
            <div className="flex items-start gap-4">
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <span className="text-xs font-bold text-slate-400">#{index + 1}</span>
                    <div className="w-11 h-11 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-sm font-bold shadow-sm">{initials}</div>
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div>
                            <h4 className="font-bold text-slate-900 dark:text-white text-base leading-tight">{match.full_name}</h4>
                            <span className={`inline-flex items-center gap-1.5 mt-1 text-xs font-semibold px-2 py-0.5 rounded-full ${meta.color} ${meta.bg} border ${meta.border}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />{meta.label}
                            </span>
                        </div>
                        <div className="flex flex-col items-center flex-shrink-0">
                            <span className={`text-3xl font-black ${scoreColor}`}>{score}</span>
                            <span className="text-[10px] text-slate-400 uppercase tracking-wider">puntos</span>
                        </div>
                    </div>
                </div>
            </div>
            {match.explanation && (
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 italic border-l-2 border-slate-300 dark:border-slate-600 pl-3">"{match.explanation}"</p>
            )}
            <div className="mt-4 space-y-2.5">
                <ScoreBar label="Habilidades"  value={match.skills_score}     color="bg-primary" />
                <ScoreBar label="Experiencia"  value={match.experience_score}  color="bg-emerald-500" />
                <ScoreBar label="Educación"    value={match.education_score}   color="bg-violet-500" />
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
                {match.bonus_skills?.length > 0 && (
                    <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold uppercase tracking-wider mr-1">✓</span>
                        {match.bonus_skills.slice(0, 3).map((s, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 text-xs font-medium">{s}</span>
                        ))}
                    </div>
                )}
                {match.missing_skills?.length > 0 && (
                    <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[11px] text-red-500 font-semibold uppercase tracking-wider mr-1">✗</span>
                        {match.missing_skills.slice(0, 3).map((s, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-xs font-medium">{s}</span>
                        ))}
                    </div>
                )}
            </div>
            <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
                <Link href={`/candidates/${match.candidate_id}`} className="flex items-center justify-center gap-2 w-full px-4 py-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-primary hover:text-white hover:border-primary transition-all">
                    Ver perfil completo
                    <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </Link>
            </div>
        </div>
    );
}

const LOADING_STEPS = ["Recuperando CVs del puesto...", "Analizando perfil de cada candidato con IA...", "Clasificando por compatibilidad..."];

function MatchLoadingState({ candidateCount }: { candidateCount?: number }) {
    const [step, setStep] = useState(0);
    useEffect(() => {
        const t1 = setTimeout(() => setStep(1), 800);
        const t2 = setTimeout(() => setStep(2), candidateCount ? candidateCount * 1200 : 3000);
        return () => { clearTimeout(t1); clearTimeout(t2); };
    }, [candidateCount]);
    return (
        <div className="py-10 flex flex-col items-center gap-5">
            <div className="relative">
                <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                    <span className="material-symbols-outlined text-[28px] text-primary animate-spin">psychology</span>
                </div>
                <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-primary"></span>
                </span>
            </div>
            <div className="text-center">
                <p className="font-semibold text-slate-900 dark:text-white">Analizando candidatos con IA</p>
                {candidateCount != null && <p className="text-sm text-slate-500 mt-1">{candidateCount} CV{candidateCount !== 1 ? "s" : ""} para evaluar</p>}
            </div>
            <div className="w-full max-w-xs space-y-3">
                {LOADING_STEPS.map((s, i) => (
                    <div key={i} className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 ${i < step ? "bg-emerald-500" : i === step ? "bg-primary animate-pulse" : "bg-slate-200 dark:bg-slate-700"}`}>
                            {i < step && <span className="material-symbols-outlined text-white text-[14px]">check</span>}
                        </div>
                        <span className={`text-sm transition-all ${i <= step ? "text-slate-700 dark:text-slate-200 font-medium" : "text-slate-400"}`}>{s}</span>
                    </div>
                ))}
            </div>
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

    // AI match state
    const [matches, setMatches] = useState<MatchResult[]>([]);
    const [matchLoading, setMatchLoading] = useState(false);
    const [showMatches, setShowMatches] = useState(false);
    const [matchLimit, setMatchLimit] = useState(10);

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
            const [jobRes, candRes] = await Promise.all([
                jobsApi.get(jobId),
                candidatesApi.list(1, 100, jobId),
            ]);
            setJob(jobRes.data);
            setCandidates(candRes.data.items || []);
        } catch (e: any) {
            setError("No se pudo cargar la convocatoria");
        } finally {
            setLoading(false);
        }
    }

    async function runMatch(limit = matchLimit) {
        setMatchLimit(limit);
        setShowMatches(true);
        setMatchLoading(true);
        setMatches([]);
        try {
            const res = await searchApi.match(jobId, limit);
            setMatches(res.data.matches || []);
        } catch {
            setMatches([]);
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
            setDeletingId(null);
            // Update job candidate count
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

    const topCount = matches.filter(m => m.recommendation === "Altamente recomendado" || m.recommendation === "Buena opción").length;
    const isAdmin = user?.role === "admin";

    // ── Render ───────────────────────────────────────────────────────────────

    return (
        <div className="space-y-6 max-w-5xl">

            {/* Breadcrumb + back */}
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
                        <button
                            onClick={() => runMatch()}
                            disabled={candidates.length === 0}
                            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <span className="material-symbols-outlined text-[18px]">psychology</span>
                            Analizar con IA
                        </button>

                        {/* More actions menu */}
                        <MoreMenu
                            status={job.status}
                            onClose={handleCloseJob}
                            onDelete={() => setShowDeleteJobConfirm(true)}
                        />
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
                {/* Description + objectives */}
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

                {/* Skills */}
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

            {/* ── AI Match Results ── */}
            {showMatches && (
                <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <span className="material-symbols-outlined text-primary text-[22px]">psychology</span>
                            <div>
                                <p className="font-bold text-slate-900 dark:text-white">Análisis IA — Compatibilidad de candidatos</p>
                                {!matchLoading && matches.length > 0 && (
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {matches.length} analizados
                                        {topCount > 0 && <span className="ml-2 text-emerald-600 dark:text-emerald-400">· {topCount} recomendados</span>}
                                    </p>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {!matchLoading && (
                                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                                    <span className="text-xs text-slate-400 px-1 font-medium">Top</span>
                                    {[5, 10, 20].map(n => (
                                        <button
                                            key={n}
                                            onClick={() => runMatch(n)}
                                            className={`px-2.5 py-1 rounded-md text-xs font-bold transition-colors ${matchLimit === n ? "bg-white dark:bg-slate-700 text-primary shadow-sm" : "text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"}`}
                                        >{n}</button>
                                    ))}
                                </div>
                            )}
                            <button onClick={() => setShowMatches(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-500 transition-colors">
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>
                    </div>
                    <div className="p-6">
                        {matchLoading ? (
                            <MatchLoadingState candidateCount={candidates.length} />
                        ) : matches.length === 0 ? (
                            <div className="text-center py-10">
                                <span className="material-symbols-outlined text-[48px] text-slate-300 dark:text-slate-600 block mb-3">person_off</span>
                                <p className="text-slate-500">Sin candidatos para analizar. Importa CVs primero.</p>
                            </div>
                        ) : (
                            <>
                                <div className="flex flex-wrap gap-2 mb-5 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                                    {Object.entries(RECOMMENDATION_META).map(([key, m]) => {
                                        const count = matches.filter(x => x.recommendation === key).length;
                                        if (count === 0) return null;
                                        return (
                                            <span key={key} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${m.color} ${m.bg} ${m.border}`}>
                                                <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />{count} {key}
                                            </span>
                                        );
                                    })}
                                </div>
                                <div className="space-y-4">
                                    {matches.map((m, i) => <CandidateMatchCard key={m.candidate_id} match={m} index={i} />)}
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

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
                            Se eliminará <strong>"{job.title}"</strong>. Los CVs ya procesados no se eliminarán — quedarán sin asignación de puesto.
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
            {/* Avatar */}
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                {initials}
            </div>

            {/* Name + skills */}
            <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900 dark:text-white text-sm truncate">{candidate.full_name}</p>
                {candidate.skills.length > 0 && (
                    <p className="text-xs text-slate-400 mt-0.5 truncate">
                        {candidate.skills.slice(0, 4).join(" · ")}{candidate.skills.length > 4 ? ` +${candidate.skills.length - 4}` : ""}
                    </p>
                )}
            </div>

            {/* Status select */}
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

            {/* Actions */}
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
        function handler(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        }
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    return (
        <div className="relative" ref={ref}>
            <button
                onClick={() => setOpen(v => !v)}
                className="flex items-center justify-center w-9 h-9 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            >
                <span className="material-symbols-outlined text-[20px]">more_vert</span>
            </button>
            {open && (
                <div className="absolute right-0 top-10 z-20 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg py-1 min-w-[180px]">
                    {status === "active" && (
                        <button
                            onClick={() => { setOpen(false); onClose(); }}
                            className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined text-[18px] text-amber-500">pause_circle</span>
                            Cerrar convocatoria
                        </button>
                    )}
                    {status === "closed" && (
                        <button
                            onClick={() => { setOpen(false); onClose(); }}
                            className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined text-[18px] text-emerald-500">play_circle</span>
                            Reabrir convocatoria
                        </button>
                    )}
                    <div className="border-t border-slate-100 dark:border-slate-700 my-1" />
                    <button
                        onClick={() => { setOpen(false); onDelete(); }}
                        className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">delete_forever</span>
                        Eliminar convocatoria
                    </button>
                </div>
            )}
        </div>
    );
}

export default JobDetail;
