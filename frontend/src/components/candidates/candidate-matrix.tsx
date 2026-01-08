"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { RadarComparison } from "./radar-comparison";
import { candidatesApi, Candidate } from "@/lib/api";

// Types
interface CandidateMatch {
    id: string;
    fullName: string;
    currentRole: string;
    email?: string;
    overallScore: number;
    experienceScore: number;
    educationScore: number;
    skillsScore: number;
    explanation: string;
    missingSkills: string[];
    bonusSkills: string[];
    skills: string[];
    experienceYears: number;
}

interface CandidateRowProps {
    candidate: CandidateMatch;
    jobTitle: string;
}

// Convert API candidate to CandidateMatch format
function toCandidateMatch(c: Candidate): CandidateMatch {
    const skillsScore = Math.min(c.skills.length * 10, 100);
    const experienceScore = Math.min(c.total_experience_years * 15, 100);
    const educationScore = 70; // Default since we don't have education scoring
    const overallScore = Math.round((skillsScore + experienceScore + educationScore) / 3);

    return {
        id: c.id,
        fullName: c.full_name,
        currentRole: c.summary?.slice(0, 50) || "Candidato",
        email: c.email,
        overallScore,
        experienceScore,
        educationScore,
        skillsScore,
        explanation: c.summary || "Candidato procesado automáticamente por el sistema.",
        missingSkills: [],
        bonusSkills: c.skills.slice(0, 3),
        skills: c.skills,
        experienceYears: c.total_experience_years,
    };
}

// Score Badge Component
function ScoreBadge({ score }: { score: number }) {
    const getScoreColor = (s: number) => {
        if (s >= 80) return "text-emerald-400 bg-emerald-500/20 border-emerald-500/30";
        if (s >= 60) return "text-green-400 bg-green-500/20 border-green-500/30";
        if (s >= 40) return "text-amber-400 bg-amber-500/20 border-amber-500/30";
        return "text-rose-400 bg-rose-500/20 border-rose-500/30";
    };

    return (
        <div className={cn(
            "w-14 h-14 rounded-full border flex items-center justify-center text-xl font-bold",
            getScoreColor(score)
        )}>
            {Math.round(score)}
        </div>
    );
}

// Mini Progress Bar
function MiniProgressBar({ label, value }: { label: string; value: number }) {
    const getBarColor = (v: number) => {
        if (v >= 80) return "bg-emerald-500";
        if (v >= 60) return "bg-green-500";
        if (v >= 40) return "bg-amber-500";
        return "bg-rose-500";
    };

    return (
        <div className="space-y-1 flex-1">
            <div className="flex justify-between text-xs">
                <span className="text-slate-400">{label}</span>
                <span className="text-white">{Math.round(value)}%</span>
            </div>
            <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                    className={cn("h-full rounded-full transition-all", getBarColor(value))}
                    style={{ width: `${value}%` }}
                />
            </div>
        </div>
    );
}

// Expandable Candidate Row
function CandidateRow({ candidate, jobTitle }: CandidateRowProps) {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="border border-[#334155] rounded-xl overflow-hidden bg-[#1e293b] hover:border-[#135bec]/30 transition-all">
            {/* Main Row */}
            <div
                className="p-4 flex items-center gap-4 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                {/* Avatar */}
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#135bec]/50 to-purple-500/50 flex items-center justify-center flex-shrink-0">
                    <span className="text-lg font-medium text-white">
                        {candidate.fullName.split(" ").map(n => n[0]).join("")}
                    </span>
                </div>

                {/* Name & Role */}
                <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-white truncate">{candidate.fullName}</h3>
                    <p className="text-sm text-slate-400 truncate">{candidate.currentRole}</p>
                </div>

                {/* Overall Score */}
                <ScoreBadge score={candidate.overallScore} />

                {/* Mini Score Breakdown */}
                <div className="hidden lg:flex gap-4 w-64">
                    <MiniProgressBar label="Exp" value={candidate.experienceScore} />
                    <MiniProgressBar label="Edu" value={candidate.educationScore} />
                    <MiniProgressBar label="Skills" value={candidate.skillsScore} />
                </div>

                {/* Status Badge */}
                <div className="hidden md:block">
                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
                        Nuevo
                    </span>
                </div>

                {/* Expand Icon */}
                <button className="p-2 rounded-lg hover:bg-slate-700 transition-colors">
                    <span className="material-symbols-outlined text-slate-400">
                        {expanded ? "expand_less" : "expand_more"}
                    </span>
                </button>
            </div>

            {/* Expanded Content */}
            {expanded && (
                <div className="border-t border-[#334155] p-6 bg-slate-800/30">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Left: Radar Chart */}
                        <div>
                            <h4 className="font-medium text-white mb-4">Comparación de Perfil</h4>
                            <RadarComparison
                                candidateName={candidate.fullName}
                                data={[
                                    { axis: "Habilidades Técnicas", candidate: candidate.skillsScore, ideal: 100 },
                                    { axis: "Experiencia", candidate: candidate.experienceScore, ideal: 100 },
                                    { axis: "Educación", candidate: candidate.educationScore, ideal: 100 },
                                    { axis: "Liderazgo", candidate: 70, ideal: 80 },
                                    { axis: "Comunicación", candidate: 75, ideal: 85 },
                                ]}
                            />
                        </div>

                        {/* Right: Skills & Explanation */}
                        <div className="space-y-4">
                            {/* AI Explanation */}
                            <div className="p-4 rounded-lg bg-[#135bec]/5 border border-[#135bec]/20">
                                <h4 className="font-medium text-[#135bec] mb-2">Resumen del Candidato</h4>
                                <p className="text-sm text-slate-400 leading-relaxed">
                                    {candidate.explanation}
                                </p>
                            </div>

                            {/* Skills */}
                            <div>
                                <h5 className="text-sm font-medium text-emerald-400 mb-2 flex items-center gap-1">
                                    <span className="material-symbols-outlined text-[16px]">check_circle</span>
                                    Habilidades Detectadas
                                </h5>
                                <div className="flex flex-wrap gap-1">
                                    {candidate.skills.length > 0 ? (
                                        candidate.skills.map((skill, i) => (
                                            <span
                                                key={i}
                                                className="inline-flex px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                            >
                                                {skill}
                                            </span>
                                        ))
                                    ) : (
                                        <p className="text-xs text-slate-500">Sin habilidades detectadas</p>
                                    )}
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-2 pt-4">
                                <button className="flex-1 py-2 px-4 rounded-lg bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 transition-colors">
                                    Programar Entrevista
                                </button>
                                <button className="py-2 px-4 rounded-lg border border-[#334155] hover:bg-slate-700 transition-colors text-slate-300">
                                    Ver CV Original
                                </button>
                                <button className="py-2 px-4 rounded-lg border border-[#334155] hover:bg-slate-700 transition-colors text-slate-400">
                                    <span className="material-symbols-outlined text-[20px]">mail</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// Main Candidate Matrix Component
interface CandidateMatrixProps {
    jobId?: string;
    jobTitle?: string;
}

export function CandidateMatrix({ jobId, jobTitle = "Todos los candidatos" }: CandidateMatrixProps) {
    const [candidates, setCandidates] = useState<CandidateMatch[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        async function fetchCandidates() {
            try {
                setLoading(true);
                const response = await candidatesApi.list(1, 50);
                const apiCandidates = response.data.items.map(toCandidateMatch);
                setCandidates(apiCandidates);
            } catch (err: any) {
                console.error("Failed to fetch candidates:", err);
                setError("No se pudo conectar con el servidor. Usando datos de ejemplo.");
                // Fallback to mock data
                setCandidates([
                    {
                        id: "1",
                        fullName: "Candidato Demo",
                        currentRole: "Ejemplo de candidato",
                        overallScore: 75,
                        experienceScore: 70,
                        educationScore: 80,
                        skillsScore: 75,
                        explanation: "Este es un candidato de ejemplo. Sube CVs reales en el Centro de Datos.",
                        missingSkills: [],
                        bonusSkills: ["Demo"],
                        skills: ["Python", "JavaScript"],
                        experienceYears: 3,
                    },
                ]);
            } finally {
                setLoading(false);
            }
        }
        fetchCandidates();
    }, [jobId]);

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <span className="material-symbols-outlined text-[32px] text-slate-400 animate-spin">sync</span>
                <span className="ml-3 text-slate-400">Cargando candidatos...</span>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-semibold text-white">Matriz de Candidatos</h2>
                    <p className="text-slate-400 text-sm">
                        {candidates.length} candidato(s) • <span className="text-[#135bec]">{jobTitle}</span>
                    </p>
                </div>
                <div className="flex gap-2">
                    <select className="px-3 py-2 rounded-lg bg-[#1e293b] border border-[#334155] text-sm text-slate-300 focus:outline-none focus:border-[#135bec]">
                        <option>Ordenar por Puntuación</option>
                        <option>Ordenar por Experiencia</option>
                        <option>Ordenar por Fecha</option>
                    </select>
                </div>
            </div>

            {error && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400 text-sm">
                    {error}
                </div>
            )}

            {/* Candidate List */}
            {candidates.length > 0 ? (
                <div className="space-y-3">
                    {candidates.map((candidate) => (
                        <CandidateRow
                            key={candidate.id}
                            candidate={candidate}
                            jobTitle={jobTitle}
                        />
                    ))}
                </div>
            ) : (
                <div className="text-center py-12 text-slate-500">
                    <span className="material-symbols-outlined text-[48px] block mb-3">person_search</span>
                    <p>No hay candidatos aún. Sube CVs en el Centro de Datos.</p>
                </div>
            )}
        </div>
    );
}
