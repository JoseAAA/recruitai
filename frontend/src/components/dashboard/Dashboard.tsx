"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { statsApi, DashboardStats, api } from "@/lib/api";

// Types for AI-powered matches
interface TopMatch {
    candidate_id: string;
    candidate_name: string;
    job_id: string;
    job_title: string;
    match_score: number;
    skills_match: string[];
    missing_skills: string[];
    recommendation: string;
}

interface JobWithMatches {
    job_id: string;
    job_title: string;
    required_skills: string[];
    top_candidates: Array<{
        candidate_id: string;
        candidate_name: string;
        match_score: number;
        recommendation: string;
    }>;
}

interface TopMatchesData {
    top_candidates: TopMatch[];
    jobs_with_matches: JobWithMatches[];
    star_candidates: TopMatch[];
    total_pending_review: number;
}

const Dashboard: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [topMatches, setTopMatches] = useState<TopMatchesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchData() {
            try {
                setLoading(true);

                // Fetch dashboard stats and top matches in parallel
                const [statsRes, matchesRes] = await Promise.all([
                    statsApi.dashboard(),
                    api.get<TopMatchesData>("/stats/top-matches").catch(() => ({ data: null }))
                ]);

                setStats(statsRes.data);
                setTopMatches(matchesRes.data);
            } catch (err: any) {
                console.error("Failed to fetch dashboard data:", err);
                setError("No se pudo conectar con el servidor");
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                <p className="text-slate-400">Cargando dashboard inteligente...</p>
            </div>
        );
    }

    const getScoreColor = (score: number) => {
        if (score >= 85) return "text-emerald-500 bg-emerald-500/20";
        if (score >= 70) return "text-blue-500 bg-blue-500/20";
        if (score >= 50) return "text-amber-500 bg-amber-500/20";
        return "text-slate-500 bg-slate-500/20";
    };

    return (
        <>
            {error && (
                <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400">
                    {error}
                </div>
            )}

            {/* Star Candidates Alert */}
            {topMatches?.star_candidates && topMatches.star_candidates.length > 0 && (
                <div className="mb-6 p-4 bg-gradient-to-r from-amber-500/10 to-emerald-500/10 border border-amber-500/30 rounded-xl">
                    <div className="flex items-center gap-3 mb-3">
                        <span className="material-symbols-outlined text-[24px] text-amber-400 animate-pulse">star</span>
                        <h3 className="font-bold text-amber-400">¡Candidatos Estrella Detectados!</h3>
                        <span className="px-2 py-0.5 bg-amber-500/20 rounded text-xs font-bold text-amber-400">
                            {topMatches.star_candidates.length} con +85% match
                        </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {topMatches.star_candidates.slice(0, 3).map((match) => (
                            <Link
                                key={`${match.candidate_id}-${match.job_id}`}
                                href={`/candidates/${match.candidate_id}`}
                                className="flex items-center gap-3 p-3 rounded-lg bg-white/50 dark:bg-slate-800/50 hover:bg-white dark:hover:bg-slate-700 transition-colors"
                            >
                                <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                                    <span className="material-symbols-outlined text-amber-500">person</span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="font-semibold text-slate-900 dark:text-white text-sm truncate">
                                        {match.candidate_name}
                                    </p>
                                    <p className="text-xs text-slate-500 truncate">
                                        Para: {match.job_title}
                                    </p>
                                </div>
                                <span className="px-2 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-500">
                                    {match.match_score}%
                                </span>
                            </Link>
                        ))}
                    </div>
                </div>
            )}

            {/* Main Stats Row */}
            <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-primary/10">
                            <span className="material-symbols-outlined text-[24px] text-primary">groups</span>
                        </div>
                        <span className="text-sm text-slate-500">Total Candidatos</span>
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white">{stats?.total_candidates || 0}</h3>
                </div>

                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-emerald-500/10">
                            <span className="material-symbols-outlined text-[24px] text-emerald-500">work</span>
                        </div>
                        <span className="text-sm text-slate-500">Vacantes Activas</span>
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white">{stats?.active_jobs || 0}</h3>
                </div>

                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-amber-500/10">
                            <span className="material-symbols-outlined text-[24px] text-amber-500">pending_actions</span>
                        </div>
                        <span className="text-sm text-slate-500">Pendientes de Revisión</span>
                    </div>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white">{topMatches?.total_pending_review || 0}</h3>
                </div>

                <div className="p-5 rounded-xl bg-gradient-to-br from-primary/10 to-purple-500/10 border border-primary/30 shadow-sm">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 rounded-lg bg-primary/20">
                            <span className="material-symbols-outlined text-[24px] text-primary">auto_awesome</span>
                        </div>
                        <span className="text-sm text-primary font-medium">IA Activa</span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">Matching Automático</h3>
                </div>
            </section>

            {/* AI-Powered: Top 5 to Review Today */}
            <section className="mb-6">
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-primary/10">
                                <span className="material-symbols-outlined text-[24px] text-primary">psychology</span>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                    Top 5 Candidatos para Revisar Hoy
                                </h3>
                                <p className="text-sm text-slate-500">Recomendados por IA según tus vacantes activas</p>
                            </div>
                        </div>
                    </div>

                    {topMatches?.top_candidates && topMatches.top_candidates.length > 0 ? (
                        <div className="space-y-3">
                            {topMatches.top_candidates.map((match, index) => (
                                <Link
                                    key={`${match.candidate_id}-${match.job_id}`}
                                    href={`/candidates/${match.candidate_id}`}
                                    className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all group border border-transparent hover:border-primary/30"
                                >
                                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10 text-primary font-bold">
                                        {index + 1}
                                    </div>
                                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center flex-shrink-0">
                                        <span className="text-white font-bold">
                                            {match.candidate_name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                                        </span>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="font-bold text-slate-900 dark:text-white">
                                            {match.candidate_name}
                                        </p>
                                        <p className="text-sm text-slate-500">
                                            Para: <span className="text-primary">{match.job_title}</span>
                                        </p>
                                        <p className="text-xs text-slate-400 mt-1">
                                            {match.recommendation}
                                        </p>
                                    </div>
                                    <div className="text-right">
                                        <span className={`px-3 py-1.5 rounded-lg text-sm font-bold ${getScoreColor(match.match_score)}`}>
                                            {match.match_score}% match
                                        </span>
                                        {match.skills_match.length > 0 && (
                                            <p className="text-xs text-emerald-500 mt-1">
                                                ✓ {match.skills_match.slice(0, 2).join(", ")}
                                            </p>
                                        )}
                                    </div>
                                    <span className="material-symbols-outlined text-slate-400 group-hover:text-primary transition-colors">
                                        chevron_right
                                    </span>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-slate-500">
                            <span className="material-symbols-outlined text-[48px] block mb-3 text-slate-300">search_off</span>
                            <p className="font-medium">No hay matches calculados aún</p>
                            <p className="text-sm mt-1">Sube CVs y crea vacantes para ver recomendaciones</p>
                            <div className="flex gap-3 justify-center mt-4">
                                <Link href="/data" className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-blue-600">
                                    Subir CVs
                                </Link>
                                <Link href="/jobs" className="px-4 py-2 border border-slate-300 text-slate-600 rounded-lg hover:bg-slate-50">
                                    Crear Vacante
                                </Link>
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* Jobs with their best matches */}
            {topMatches?.jobs_with_matches && topMatches.jobs_with_matches.length > 0 && (
                <section className="mb-6">
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                        <span className="material-symbols-outlined text-emerald-500">work</span>
                        Vacantes con Mejores Candidatos
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {topMatches.jobs_with_matches.map((job) => (
                            <div
                                key={job.job_id}
                                className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm"
                            >
                                <div className="flex items-center justify-between mb-3">
                                    <h4 className="font-bold text-slate-900 dark:text-white">{job.job_title}</h4>
                                    <Link
                                        href={`/jobs`}
                                        className="text-xs text-primary hover:underline"
                                    >
                                        Ver vacante →
                                    </Link>
                                </div>
                                {job.top_candidates.length > 0 ? (
                                    <div className="space-y-2">
                                        {job.top_candidates.map((candidate, i) => (
                                            <Link
                                                key={candidate.candidate_id}
                                                href={`/candidates/${candidate.candidate_id}`}
                                                className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                            >
                                                <span className="text-xs text-slate-400 w-4">{i + 1}.</span>
                                                <span className="flex-1 text-sm text-slate-700 dark:text-slate-300 truncate">
                                                    {candidate.candidate_name}
                                                </span>
                                                <span className={`px-2 py-0.5 rounded text-xs font-bold ${getScoreColor(candidate.match_score)}`}>
                                                    {candidate.match_score}%
                                                </span>
                                            </Link>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-slate-500">No hay candidatos aún</p>
                                )}
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* Quick Actions */}
            <section>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Acciones Rápidas</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Link
                        href="/data"
                        className="flex flex-col items-center gap-3 p-6 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-lg hover:border-primary/50 transition-all group"
                    >
                        <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                            <span className="material-symbols-outlined text-[28px] text-primary">upload_file</span>
                        </div>
                        <h3 className="font-semibold text-slate-900 dark:text-white">Subir CVs</h3>
                        <p className="text-sm text-slate-500 text-center">Importa candidatos y la IA los rankea automáticamente</p>
                    </Link>

                    <Link
                        href="/jobs"
                        className="flex flex-col items-center gap-3 p-6 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-lg hover:border-emerald-500/50 transition-all group"
                    >
                        <div className="w-14 h-14 rounded-full bg-emerald-500/10 flex items-center justify-center group-hover:bg-emerald-500/20 transition-colors">
                            <span className="material-symbols-outlined text-[28px] text-emerald-500">add_circle</span>
                        </div>
                        <h3 className="font-semibold text-slate-900 dark:text-white">Nueva Vacante</h3>
                        <p className="text-sm text-slate-500 text-center">Crea un puesto y recibe candidatos recomendados</p>
                    </Link>

                    <Link
                        href="/candidates"
                        className="flex flex-col items-center gap-3 p-6 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-lg hover:border-indigo-500/50 transition-all group"
                    >
                        <div className="w-14 h-14 rounded-full bg-indigo-500/10 flex items-center justify-center group-hover:bg-indigo-500/20 transition-colors">
                            <span className="material-symbols-outlined text-[28px] text-indigo-500">person_search</span>
                        </div>
                        <h3 className="font-semibold text-slate-900 dark:text-white">Ver Todos</h3>
                        <p className="text-sm text-slate-500 text-center">Explora la base completa de candidatos</p>
                    </Link>
                </div>
            </section>
        </>
    );
};

export default Dashboard;
