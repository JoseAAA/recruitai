"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jobsApi, searchApi, JobProfile, MatchResult } from "@/lib/api";

// ── Helpers ─────────────────────────────────────────────────────────────────

const RECOMMENDATION_META: Record<string, { label: string; color: string; bg: string; border: string; dot: string }> = {
    "Altamente recomendado": {
        label: "Altamente recomendado",
        color: "text-emerald-700 dark:text-emerald-300",
        bg: "bg-emerald-50 dark:bg-emerald-900/30",
        border: "border-emerald-200 dark:border-emerald-700",
        dot: "bg-emerald-500",
    },
    "Buena opción": {
        label: "Buena opción",
        color: "text-blue-700 dark:text-blue-300",
        bg: "bg-blue-50 dark:bg-blue-900/30",
        border: "border-blue-200 dark:border-blue-700",
        dot: "bg-blue-500",
    },
    "Considerar": {
        label: "Considerar",
        color: "text-amber-700 dark:text-amber-300",
        bg: "bg-amber-50 dark:bg-amber-900/30",
        border: "border-amber-200 dark:border-amber-700",
        dot: "bg-amber-500",
    },
    "No recomendado": {
        label: "No recomendado",
        color: "text-slate-500 dark:text-slate-400",
        bg: "bg-slate-50 dark:bg-slate-800/50",
        border: "border-slate-200 dark:border-slate-700",
        dot: "bg-slate-400",
    },
};

function getMeta(recommendation: string) {
    return RECOMMENDATION_META[recommendation] ?? RECOMMENDATION_META["Considerar"];
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div>
            <div className="flex justify-between items-center mb-1">
                <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
                <span className="text-xs font-bold text-slate-700 dark:text-slate-300">{Math.round(value)}%</span>
            </div>
            <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                    className={`h-full ${color} rounded-full transition-all duration-700`}
                    style={{ width: `${value}%` }}
                />
            </div>
        </div>
    );
}

function CandidateMatchCard({ match, index }: { match: MatchResult; index: number }) {
    const meta = getMeta(match.recommendation);
    const score = Math.round(match.overall_score);
    const initials = match.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

    const scoreColor =
        score >= 75 ? "text-emerald-600" :
        score >= 55 ? "text-blue-600" :
        score >= 35 ? "text-amber-600" :
        "text-slate-500";

    const barColors = ["bg-primary", "bg-emerald-500", "bg-violet-500"];

    return (
        <div className={`rounded-xl border ${meta.border} ${meta.bg} p-5 transition-all`}>
            {/* Header row */}
            <div className="flex items-start gap-4">
                {/* Rank + Avatar */}
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <span className="text-xs font-bold text-slate-400">#{index + 1}</span>
                    <div className="w-11 h-11 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-sm font-bold shadow-sm">
                        {initials}
                    </div>
                </div>

                {/* Name + recommendation badge + score */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                        <div>
                            <h4 className="font-bold text-slate-900 dark:text-white text-base leading-tight">
                                {match.full_name}
                            </h4>
                            <span className={`inline-flex items-center gap-1.5 mt-1 text-xs font-semibold px-2 py-0.5 rounded-full ${meta.color} ${meta.bg} border ${meta.border}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                                {meta.label}
                            </span>
                        </div>
                        {/* Score circle */}
                        <div className="flex flex-col items-center flex-shrink-0">
                            <span className={`text-3xl font-black ${scoreColor}`}>{score}</span>
                            <span className="text-[10px] text-slate-400 uppercase tracking-wider">puntos</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* AI Explanation */}
            {match.explanation && (
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 italic border-l-2 border-slate-300 dark:border-slate-600 pl-3">
                    "{match.explanation}"
                </p>
            )}

            {/* Score bars */}
            <div className="mt-4 space-y-2.5">
                <ScoreBar label="Habilidades" value={match.skills_score} color={barColors[0]} />
                <ScoreBar label="Experiencia" value={match.experience_score} color={barColors[1]} />
                <ScoreBar label="Educación" value={match.education_score} color={barColors[2]} />
            </div>

            {/* Skills summary */}
            <div className="mt-4 flex flex-wrap gap-3">
                {match.bonus_skills && match.bonus_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold uppercase tracking-wider mr-1">✓</span>
                        {match.bonus_skills.slice(0, 3).map((s, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
                                {s}
                            </span>
                        ))}
                    </div>
                )}
                {match.missing_skills && match.missing_skills.length > 0 && (
                    <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-[11px] text-red-500 font-semibold uppercase tracking-wider mr-1">✗</span>
                        {match.missing_skills.slice(0, 3).map((s, i) => (
                            <span key={i} className="px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-xs font-medium">
                                {s}
                            </span>
                        ))}
                    </div>
                )}
            </div>

            {/* CTA */}
            <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
                <Link
                    href={`/candidates/${match.candidate_id}`}
                    className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 text-sm font-medium hover:bg-primary hover:text-white hover:border-primary transition-all"
                >
                    Ver perfil
                    <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </Link>
            </div>
        </div>
    );
}

// ── Loading steps component ──────────────────────────────────────────────────

const LOADING_STEPS = [
    "Recuperando CVs del puesto...",
    "Analizando perfil de cada candidato con IA...",
    "Clasificando por compatibilidad...",
];

function MatchLoadingState({ candidateCount }: { candidateCount?: number }) {
    const [step, setStep] = useState(0);

    useEffect(() => {
        const timers = [
            setTimeout(() => setStep(1), 800),
            setTimeout(() => setStep(2), candidateCount ? candidateCount * 1200 : 3000),
        ];
        return () => timers.forEach(clearTimeout);
    }, [candidateCount]);

    return (
        <div className="py-12 flex flex-col items-center gap-6">
            <div className="relative">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <span className="material-symbols-outlined text-[32px] text-primary animate-spin">
                        psychology
                    </span>
                </div>
                <span className="absolute -top-1 -right-1 flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-primary"></span>
                </span>
            </div>

            <div className="text-center">
                <p className="font-semibold text-slate-900 dark:text-white">Analizando candidatos con IA</p>
                {candidateCount && (
                    <p className="text-sm text-slate-500 mt-1">{candidateCount} CV{candidateCount !== 1 ? "s" : ""} para evaluar</p>
                )}
            </div>

            <div className="w-full max-w-xs space-y-3">
                {LOADING_STEPS.map((s, i) => (
                    <div key={i} className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500 ${
                            i < step ? "bg-emerald-500" :
                            i === step ? "bg-primary animate-pulse" :
                            "bg-slate-200 dark:bg-slate-700"
                        }`}>
                            {i < step && (
                                <span className="material-symbols-outlined text-white text-[14px]">check</span>
                            )}
                        </div>
                        <span className={`text-sm transition-all ${
                            i <= step ? "text-slate-700 dark:text-slate-200 font-medium" : "text-slate-400"
                        }`}>
                            {s}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ── Main component ───────────────────────────────────────────────────────────

const JobsList: React.FC = () => {
    const router = useRouter();
    const [jobs, setJobs] = useState<JobProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedJob, setSelectedJob] = useState<JobProfile | null>(null);
    const [matches, setMatches] = useState<MatchResult[]>([]);
    const [matchLoading, setMatchLoading] = useState(false);
    const [showMatchModal, setShowMatchModal] = useState(false);
    const [matchLimit, setMatchLimit] = useState<number>(10);
    const modalRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchJobs();
    }, []);

    async function fetchJobs() {
        try {
            setLoading(true);
            const response = await jobsApi.list();
            setJobs(response.data.items || []);
        } catch (err: any) {
            console.error("Failed to fetch jobs:", err);
            setError("No se pudo cargar los perfiles de puesto");
        } finally {
            setLoading(false);
        }
    }

    async function findCandidates(job: JobProfile, limit?: number) {
        const useLimit = limit ?? matchLimit;
        setSelectedJob(job);
        setShowMatchModal(true);
        setMatchLoading(true);
        setMatches([]);

        try {
            const response = await searchApi.match(job.id, useLimit);
            setMatches(response.data.matches || []);
        } catch (err: any) {
            console.error("Failed to find matches:", err);
            setMatches([]);
        } finally {
            setMatchLoading(false);
        }
    }

    async function changeLimit(newLimit: number) {
        setMatchLimit(newLimit);
        if (selectedJob) {
            await findCandidates(selectedJob, newLimit);
        }
    }

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                <p className="text-slate-400">Cargando perfiles de puesto...</p>
            </div>
        );
    }

    // Summary for results
    const topCount = matches.filter(
        m => m.recommendation === "Altamente recomendado" || m.recommendation === "Buena opción"
    ).length;

    return (
        <>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Perfiles de Puesto
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        {jobs.length} perfil(es) activo(s)
                    </p>
                </div>
                <Link
                    href="/jobs/new"
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 transition-colors shadow-sm shadow-blue-500/30"
                >
                    <span className="material-symbols-outlined text-[20px]">add</span>
                    Nuevo Perfil
                </Link>
            </div>

            {error && (
                <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400">
                    {error}
                </div>
            )}

            {/* Job Cards */}
            {jobs.length === 0 ? (
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-12 text-center">
                    <span className="material-symbols-outlined text-[48px] text-slate-400 block mb-3">work_off</span>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                        No hay perfiles de puesto aún
                    </h3>
                    <p className="text-slate-500 mb-4">
                        Crea tu primer perfil para comenzar a analizar candidatos
                    </p>
                    <Link
                        href="/jobs/new"
                        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        Crear Perfil
                    </Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {jobs.map((job) => (
                        <div
                            key={job.id}
                            className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm hover:shadow-lg hover:border-primary/40 transition-all flex flex-col"
                        >
                            {/* Job header */}
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex-1 min-w-0">
                                    <Link href={`/jobs/${job.id}`} className="group">
                                        <h3 className="text-lg font-bold text-slate-900 dark:text-white leading-tight group-hover:text-primary transition-colors">
                                            {job.title}
                                        </h3>
                                    </Link>
                                    {job.department && (
                                        <p className="text-sm text-slate-500 mt-0.5">{job.department}</p>
                                    )}
                                </div>
                                <span className={`ml-2 flex-shrink-0 px-2.5 py-1 rounded-full text-xs font-semibold ${
                                    job.status === "active"
                                        ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300"
                                        : "bg-slate-100 dark:bg-slate-700 text-slate-500"
                                }`}>
                                    {job.status === "active" ? "Activo" : job.status}
                                </span>
                            </div>

                            {/* CV count — the most important metric */}
                            <div className="flex items-center gap-2 py-3 px-4 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800 mb-4">
                                <span className="material-symbols-outlined text-[22px] text-indigo-500">folder_open</span>
                                <div>
                                    <span className="text-2xl font-black text-indigo-600 dark:text-indigo-300">
                                        {job.candidate_count ?? 0}
                                    </span>
                                    <span className="text-sm text-indigo-500 dark:text-indigo-400 ml-1">
                                        CV{(job.candidate_count ?? 0) !== 1 ? "s" : ""} cargado{(job.candidate_count ?? 0) !== 1 ? "s" : ""}
                                    </span>
                                </div>
                            </div>

                            {/* Requirements */}
                            <div className="space-y-2 text-sm text-slate-600 dark:text-slate-300 mb-4">
                                <div className="flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[16px] text-slate-400">work_history</span>
                                    {job.min_experience_years}+ años de experiencia
                                </div>
                                {job.education_level && (
                                    <div className="flex items-center gap-2">
                                        <span className="material-symbols-outlined text-[16px] text-slate-400">school</span>
                                        {job.education_level}
                                    </div>
                                )}
                            </div>

                            {/* Required skills (top 4) */}
                            {(job.required_skills?.length ?? 0) > 0 && (
                                <div className="mb-5">
                                    <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                                        Habilidades clave
                                    </p>
                                    <div className="flex flex-wrap gap-1">
                                        {job.required_skills.slice(0, 5).map((skill, i) => (
                                            <span key={i} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                                                {skill}
                                            </span>
                                        ))}
                                        {job.required_skills.length > 5 && (
                                            <span className="text-xs text-slate-400 self-center">
                                                +{job.required_skills.length - 5} más
                                            </span>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Actions — push to bottom */}
                            <div className="mt-auto flex flex-col gap-2">
                                <Link
                                    href={`/jobs/${job.id}`}
                                    className="flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-white font-semibold rounded-lg hover:bg-blue-600 transition-colors"
                                >
                                    <span className="material-symbols-outlined text-[20px]">folder_open</span>
                                    Ver vacante
                                </Link>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => findCandidates(job)}
                                        disabled={(job.candidate_count ?? 0) === 0}
                                        className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-medium rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        <span className="material-symbols-outlined text-[17px]">psychology</span>
                                        Analizar IA
                                    </button>
                                    <button
                                        onClick={() => router.push(`/data?job_id=${job.id}`)}
                                        className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-medium rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-sm"
                                    >
                                        <span className="material-symbols-outlined text-[17px]">upload_file</span>
                                        Importar CVs
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* ── Match Results Modal ── */}
            {showMatchModal && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center p-4 overflow-y-auto">
                    <div
                        ref={modalRef}
                        className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-3xl my-8"
                    >
                        {/* Modal header */}
                        <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-700 flex items-start justify-between gap-4">
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="material-symbols-outlined text-primary text-[20px]">psychology</span>
                                    <span className="text-xs font-bold text-primary uppercase tracking-wider">Análisis IA con qwen3.5</span>
                                </div>
                                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                                    {selectedJob?.title}
                                </h2>
                                {!matchLoading && matches.length > 0 && (
                                    <p className="text-sm text-slate-500 mt-1">
                                        <span className="font-semibold text-slate-700 dark:text-slate-200">{matches.length} candidato{matches.length !== 1 ? "s" : ""} analizados</span>
                                        {topCount > 0 && (
                                            <span className="ml-2 text-emerald-600 dark:text-emerald-400 font-medium">
                                                · {topCount} recomendado{topCount !== 1 ? "s" : ""}
                                            </span>
                                        )}
                                        {selectedJob?.candidate_count != null && (
                                            <span className="ml-2 text-indigo-500">
                                                · {selectedJob.candidate_count} CVs en el pool
                                            </span>
                                        )}
                                    </p>
                                )}
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                                {/* Top N selector */}
                                {!matchLoading && (
                                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
                                        <span className="text-xs text-slate-400 px-1 font-medium">Top</span>
                                        {[5, 10, 20].map((n) => (
                                            <button
                                                key={n}
                                                onClick={() => changeLimit(n)}
                                                className={`px-2.5 py-1 rounded-md text-xs font-bold transition-colors ${
                                                    matchLimit === n
                                                        ? "bg-white dark:bg-slate-700 text-primary shadow-sm"
                                                        : "text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                                                }`}
                                            >
                                                {n}
                                            </button>
                                        ))}
                                    </div>
                                )}
                                <button
                                    onClick={() => setShowMatchModal(false)}
                                    className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors text-slate-500"
                                >
                                    <span className="material-symbols-outlined">close</span>
                                </button>
                            </div>
                        </div>

                        {/* Modal body */}
                        <div className="p-6">
                            {matchLoading ? (
                                <MatchLoadingState candidateCount={selectedJob?.candidate_count} />
                            ) : matches.length === 0 ? (
                                <div className="text-center py-12">
                                    <span className="material-symbols-outlined text-[56px] text-slate-300 dark:text-slate-600 block mb-3">
                                        person_off
                                    </span>
                                    <h3 className="text-lg font-bold text-slate-800 dark:text-white mb-2">
                                        Sin candidatos para analizar
                                    </h3>
                                    <p className="text-slate-500 text-sm mb-5">
                                        Importa CVs a este perfil de puesto y vuelve a analizar.
                                    </p>
                                    <button
                                        onClick={() => {
                                            setShowMatchModal(false);
                                            if (selectedJob) router.push(`/data?job_id=${selectedJob.id}`);
                                        }}
                                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-white font-medium rounded-lg hover:bg-blue-600"
                                    >
                                        <span className="material-symbols-outlined text-[20px]">upload_file</span>
                                        Importar CVs a este perfil
                                    </button>
                                </div>
                            ) : (
                                <>
                                    {/* Recommendation summary legend */}
                                    <div className="flex flex-wrap gap-2 mb-5 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                                        {Object.entries(RECOMMENDATION_META).map(([key, m]) => {
                                            const count = matches.filter(x => x.recommendation === key).length;
                                            if (count === 0) return null;
                                            return (
                                                <span key={key} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${m.color} ${m.bg} ${m.border}`}>
                                                    <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
                                                    {count} {key}
                                                </span>
                                            );
                                        })}
                                    </div>

                                    {/* Candidate cards */}
                                    <div className="space-y-4">
                                        {matches.map((match, i) => (
                                            <CandidateMatchCard key={match.candidate_id} match={match} index={i} />
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default JobsList;
