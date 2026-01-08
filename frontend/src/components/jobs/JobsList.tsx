"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { jobsApi, searchApi, JobProfile, MatchResult } from "@/lib/api";

const JobsList: React.FC = () => {
    const [jobs, setJobs] = useState<JobProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedJob, setSelectedJob] = useState<JobProfile | null>(null);
    const [matches, setMatches] = useState<MatchResult[]>([]);
    const [matchLoading, setMatchLoading] = useState(false);
    const [showMatchModal, setShowMatchModal] = useState(false);

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
            setError("No se pudo cargar las vacantes");
        } finally {
            setLoading(false);
        }
    }

    async function findCandidates(job: JobProfile) {
        setSelectedJob(job);
        setShowMatchModal(true);
        setMatchLoading(true);
        setMatches([]);

        try {
            const response = await searchApi.match(job.id, 20);
            setMatches(response.data.matches || []);
        } catch (err: any) {
            console.error("Failed to find matches:", err);
            // Use fallback matching from candidates
            setMatches([]);
        } finally {
            setMatchLoading(false);
        }
    }

    const getScoreColor = (score: number) => {
        if (score >= 80) return "text-emerald-500";
        if (score >= 60) return "text-amber-500";
        return "text-red-400";
    };

    const getScoreBg = (score: number) => {
        if (score >= 80) return "bg-emerald-500/20";
        if (score >= 60) return "bg-amber-500/20";
        return "bg-red-500/20";
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                <p className="text-slate-400">Cargando vacantes...</p>
            </div>
        );
    }

    return (
        <>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Gestión de Vacantes
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        {jobs.length} vacante(s) en el sistema
                    </p>
                </div>
                <Link
                    href="/jobs/new"
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 transition-colors shadow-sm shadow-blue-500/30"
                >
                    <span className="material-symbols-outlined text-[20px]">add</span>
                    Nueva Vacante
                </Link>
            </div>

            {error && (
                <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400">
                    {error}
                </div>
            )}

            {/* Jobs List */}
            {jobs.length === 0 ? (
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-12 text-center">
                    <span className="material-symbols-outlined text-[48px] text-slate-400 block mb-3">work_off</span>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                        No hay vacantes aún
                    </h3>
                    <p className="text-slate-500 mb-4">
                        Crea tu primera vacante para empezar a buscar candidatos
                    </p>
                    <Link
                        href="/jobs/new"
                        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600"
                    >
                        <span className="material-symbols-outlined text-[20px]">add</span>
                        Crear Vacante
                    </Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {jobs.map((job) => (
                        <div
                            key={job.id}
                            className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm hover:shadow-lg transition-all"
                        >
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                        {job.title}
                                    </h3>
                                    {job.department && (
                                        <p className="text-sm text-slate-500">{job.department}</p>
                                    )}
                                </div>
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${job.status === "active"
                                        ? "bg-emerald-500/20 text-emerald-400"
                                        : "bg-slate-500/20 text-slate-400"
                                    }`}>
                                    {job.status === "active" ? "Activa" : job.status}
                                </span>
                            </div>

                            {/* Requirements Summary */}
                            <div className="space-y-3 mb-4">
                                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                    <span className="material-symbols-outlined text-[18px] text-slate-400">school</span>
                                    {job.education_level || "No especificado"}
                                </div>
                                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                    <span className="material-symbols-outlined text-[18px] text-slate-400">work_history</span>
                                    {job.min_experience_years}+ años experiencia
                                </div>
                            </div>

                            {/* Skills */}
                            <div className="mb-4">
                                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                                    Habilidades requeridas
                                </p>
                                <div className="flex flex-wrap gap-1">
                                    {job.required_skills?.slice(0, 4).map((skill, i) => (
                                        <span
                                            key={i}
                                            className="px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-medium"
                                        >
                                            {skill}
                                        </span>
                                    ))}
                                    {(job.required_skills?.length || 0) > 4 && (
                                        <span className="text-xs text-slate-400">
                                            +{(job.required_skills?.length || 0) - 4}
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-2 pt-4 border-t border-slate-100 dark:border-slate-700/50">
                                <button
                                    onClick={() => findCandidates(job)}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-500 text-white font-medium rounded-lg hover:bg-emerald-600 transition-colors"
                                >
                                    <span className="material-symbols-outlined text-[20px]">person_search</span>
                                    Buscar Candidatos
                                </button>
                                <button className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                                    <span className="material-symbols-outlined text-[20px]">more_vert</span>
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Match Results Modal */}
            {showMatchModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
                        {/* Modal Header */}
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                                    Candidatos para: {selectedJob?.title}
                                </h2>
                                <p className="text-sm text-slate-500">
                                    {matches.length} candidato(s) encontrado(s)
                                </p>
                            </div>
                            <button
                                onClick={() => setShowMatchModal(false)}
                                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
                            >
                                <span className="material-symbols-outlined">close</span>
                            </button>
                        </div>

                        {/* Modal Content */}
                        <div className="p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
                            {matchLoading ? (
                                <div className="flex flex-col items-center justify-center py-12">
                                    <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                                    <p className="text-slate-500 mt-4">Analizando candidatos...</p>
                                </div>
                            ) : matches.length === 0 ? (
                                <div className="text-center py-12">
                                    <span className="material-symbols-outlined text-[48px] text-slate-400 block mb-3">person_off</span>
                                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">
                                        No se encontraron candidatos
                                    </h3>
                                    <p className="text-slate-500">
                                        Sube más CVs para encontrar matches
                                    </p>
                                    <Link
                                        href="/data"
                                        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 mt-4"
                                    >
                                        <span className="material-symbols-outlined text-[20px]">upload_file</span>
                                        Subir CVs
                                    </Link>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {matches.map((match, index) => (
                                        <div
                                            key={match.candidate_id}
                                            className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 border border-slate-200 dark:border-slate-700"
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Rank Badge */}
                                                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center">
                                                    <span className="text-white font-bold">#{index + 1}</span>
                                                </div>

                                                {/* Candidate Info */}
                                                <div className="flex-1">
                                                    <div className="flex items-start justify-between">
                                                        <div>
                                                            <h4 className="font-bold text-slate-900 dark:text-white">
                                                                {match.full_name}
                                                            </h4>
                                                            <p className="text-sm text-slate-500">
                                                                {match.explanation}
                                                            </p>
                                                        </div>
                                                        {/* Score */}
                                                        <div className={`px-3 py-1 rounded-full font-bold ${getScoreBg(match.overall_score)} ${getScoreColor(match.overall_score)}`}>
                                                            {Math.round(match.overall_score)}% Match
                                                        </div>
                                                    </div>

                                                    {/* Score Breakdown */}
                                                    <div className="grid grid-cols-3 gap-4 mt-4">
                                                        <div>
                                                            <p className="text-xs text-slate-500 uppercase tracking-wider">Habilidades</p>
                                                            <div className="flex items-center gap-2">
                                                                <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                                                    <div
                                                                        className="h-full bg-primary rounded-full"
                                                                        style={{ width: `${match.skills_score}%` }}
                                                                    />
                                                                </div>
                                                                <span className="text-sm font-medium">{Math.round(match.skills_score)}%</span>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <p className="text-xs text-slate-500 uppercase tracking-wider">Experiencia</p>
                                                            <div className="flex items-center gap-2">
                                                                <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                                                    <div
                                                                        className="h-full bg-emerald-500 rounded-full"
                                                                        style={{ width: `${match.experience_score}%` }}
                                                                    />
                                                                </div>
                                                                <span className="text-sm font-medium">{Math.round(match.experience_score)}%</span>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <p className="text-xs text-slate-500 uppercase tracking-wider">Educación</p>
                                                            <div className="flex items-center gap-2">
                                                                <div className="flex-1 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                                                    <div
                                                                        className="h-full bg-amber-500 rounded-full"
                                                                        style={{ width: `${match.education_score}%` }}
                                                                    />
                                                                </div>
                                                                <span className="text-sm font-medium">{Math.round(match.education_score)}%</span>
                                                            </div>
                                                        </div>
                                                    </div>

                                                    {/* Skills Gap */}
                                                    <div className="flex flex-wrap gap-4 mt-4">
                                                        {match.missing_skills?.length > 0 && (
                                                            <div>
                                                                <p className="text-xs text-red-400 uppercase tracking-wider mb-1">Falta</p>
                                                                <div className="flex flex-wrap gap-1">
                                                                    {match.missing_skills.slice(0, 3).map((skill, i) => (
                                                                        <span key={i} className="px-2 py-0.5 rounded bg-red-500/20 text-red-400 text-xs">
                                                                            {skill}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                        {match.bonus_skills?.length > 0 && (
                                                            <div>
                                                                <p className="text-xs text-emerald-400 uppercase tracking-wider mb-1">Bonus</p>
                                                                <div className="flex flex-wrap gap-1">
                                                                    {match.bonus_skills.slice(0, 3).map((skill, i) => (
                                                                        <span key={i} className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-xs">
                                                                            {skill}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export default JobsList;
