"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { candidatesApi, Candidate as ApiCandidate } from "@/lib/api";

interface CandidateDisplay {
    id: string;
    name: string;
    email: string;
    role: string;
    location: string;
    experience: string;
    experienceYears: number;
    matchScore: number;
    skills: string[];
    status: string;
}

function convertApiToDisplay(c: ApiCandidate): CandidateDisplay {
    return {
        id: c.id,
        name: c.full_name,
        email: c.email || "",
        role: c.summary?.slice(0, 40) || "Candidato",
        location: "Pendiente",
        experience: `${c.total_experience_years} años`,
        experienceYears: c.total_experience_years,
        matchScore: Math.min(c.skills.length * 12, 100),
        skills: c.skills,
        status: c.status,
    };
}

const CandidateList: React.FC = () => {
    const [candidates, setCandidates] = useState<CandidateDisplay[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [total, setTotal] = useState(0);

    // Search and Filter State
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedStatus, setSelectedStatus] = useState<string>("all");
    const [selectedSkill, setSelectedSkill] = useState<string>("all");
    const [showFilters, setShowFilters] = useState(false);

    useEffect(() => {
        async function fetchCandidates() {
            try {
                setLoading(true);
                const response = await candidatesApi.list(1, 100);
                setCandidates(response.data.items.map(convertApiToDisplay));
                setTotal(response.data.total);
            } catch (err: any) {
                console.error("Failed to fetch candidates:", err);
                setError("No se pudo cargar la lista. Verifica que el backend esté corriendo.");
            } finally {
                setLoading(false);
            }
        }
        fetchCandidates();
    }, []);

    // Extract unique skills and statuses for filter options
    const allSkills = useMemo(() => {
        const skills = new Set<string>();
        candidates.forEach(c => c.skills.forEach(s => skills.add(s)));
        return Array.from(skills).sort();
    }, [candidates]);

    const allStatuses = useMemo(() => {
        const statuses = new Set<string>();
        candidates.forEach(c => statuses.add(c.status));
        return Array.from(statuses);
    }, [candidates]);

    // Filtered candidates
    const filteredCandidates = useMemo(() => {
        return candidates.filter(c => {
            // Search by name or email
            const matchesSearch = searchQuery === "" ||
                c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                c.email.toLowerCase().includes(searchQuery.toLowerCase());

            // Filter by status
            const matchesStatus = selectedStatus === "all" || c.status === selectedStatus;

            // Filter by skill
            const matchesSkill = selectedSkill === "all" ||
                c.skills.some(s => s.toLowerCase() === selectedSkill.toLowerCase());

            return matchesSearch && matchesStatus && matchesSkill;
        });
    }, [candidates, searchQuery, selectedStatus, selectedSkill]);

    const clearFilters = () => {
        setSearchQuery("");
        setSelectedStatus("all");
        setSelectedSkill("all");
    };

    const hasActiveFilters = searchQuery !== "" || selectedStatus !== "all" || selectedSkill !== "all";

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-16 space-y-4">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
                <p className="text-slate-400">Cargando candidatos...</p>
            </div>
        );
    }

    return (
        <>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Candidatos Disponibles
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        {total} candidato(s) en tu base de datos.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Link
                        href="/data"
                        className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm"
                    >
                        <span className="material-symbols-outlined text-[20px]">upload_file</span>
                        Importar CVs
                    </Link>
                </div>
            </div>

            {/* Search and Filters Bar */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4 mb-4 shadow-sm">
                <div className="flex flex-col md:flex-row gap-4">
                    {/* Search Input */}
                    <div className="flex-1 relative">
                        <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-[20px]">
                            search
                        </span>
                        <input
                            type="text"
                            placeholder="Buscar por nombre o email..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2.5 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all"
                        />
                        {searchQuery && (
                            <button
                                onClick={() => setSearchQuery("")}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                            >
                                <span className="material-symbols-outlined text-[18px]">close</span>
                            </button>
                        )}
                    </div>

                    {/* Filter Toggle Button */}
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`flex items-center gap-2 px-4 py-2.5 border rounded-lg text-sm font-medium transition-colors ${showFilters || hasActiveFilters
                                ? "bg-primary/10 border-primary/30 text-primary"
                                : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                            }`}
                    >
                        <span className="material-symbols-outlined text-[20px]">filter_list</span>
                        Filtros
                        {hasActiveFilters && (
                            <span className="bg-primary text-white text-xs px-1.5 py-0.5 rounded-full">
                                !
                            </span>
                        )}
                    </button>
                </div>

                {/* Expanded Filters */}
                {showFilters && (
                    <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                        {/* Status Filter */}
                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Estado
                            </label>
                            <select
                                value={selectedStatus}
                                onChange={(e) => setSelectedStatus(e.target.value)}
                                className="px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                            >
                                <option value="all">Todos los estados</option>
                                {allStatuses.map(status => (
                                    <option key={status} value={status}>
                                        {status === "new" ? "Nuevo" : status === "reviewed" ? "Revisado" : status === "shortlisted" ? "Preseleccionado" : status}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Skills Filter */}
                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Habilidad
                            </label>
                            <select
                                value={selectedSkill}
                                onChange={(e) => setSelectedSkill(e.target.value)}
                                className="px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary/50"
                            >
                                <option value="all">Todas las habilidades</option>
                                {allSkills.slice(0, 20).map(skill => (
                                    <option key={skill} value={skill}>{skill}</option>
                                ))}
                            </select>
                        </div>

                        {/* Clear Filters */}
                        {hasActiveFilters && (
                            <div className="flex items-end">
                                <button
                                    onClick={clearFilters}
                                    className="flex items-center gap-1 px-3 py-2 text-sm text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                                >
                                    <span className="material-symbols-outlined text-[18px]">clear_all</span>
                                    Limpiar filtros
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Results Summary */}
            {hasActiveFilters && (
                <div className="flex items-center gap-2 mb-4 text-sm text-slate-500">
                    <span className="material-symbols-outlined text-[18px]">info</span>
                    Mostrando {filteredCandidates.length} de {candidates.length} candidatos
                </div>
            )}

            {error && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-amber-400 flex items-center gap-3 mb-4">
                    <span className="material-symbols-outlined">warning</span>
                    {error}
                </div>
            )}

            {/* Table */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    Candidato
                                </th>
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    Habilidades
                                </th>
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    Experiencia
                                </th>
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    Estado
                                </th>
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-center">
                                    Match
                                </th>
                                <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 text-right">
                                    Acciones
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                            {filteredCandidates.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="py-12 text-center">
                                        {hasActiveFilters ? (
                                            <>
                                                <span className="material-symbols-outlined text-[48px] text-slate-400 block mb-3">search_off</span>
                                                <p className="text-slate-500">No se encontraron candidatos con esos filtros.</p>
                                                <button
                                                    onClick={clearFilters}
                                                    className="text-primary hover:underline text-sm mt-2"
                                                >
                                                    Limpiar filtros
                                                </button>
                                            </>
                                        ) : (
                                            <>
                                                <span className="material-symbols-outlined text-[48px] text-slate-400 block mb-3">person_off</span>
                                                <p className="text-slate-500">No hay candidatos aún.</p>
                                                <Link href="/data" className="text-primary hover:underline text-sm mt-2 inline-block">
                                                    Sube CVs desde el Centro de Datos
                                                </Link>
                                            </>
                                        )}
                                    </td>
                                </tr>
                            ) : (
                                filteredCandidates.map((c) => (
                                    <tr
                                        key={c.id}
                                        className="group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                                    >
                                        <td className="py-4 px-6">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary/50 to-purple-500/50 flex items-center justify-center flex-shrink-0">
                                                    <span className="text-sm font-medium text-white">
                                                        {c.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                                                    </span>
                                                </div>
                                                <div>
                                                    <p className="text-sm font-semibold text-slate-900 dark:text-white">
                                                        {c.name}
                                                    </p>
                                                    <p className="text-xs text-slate-500 dark:text-slate-400">
                                                        {c.email || "Sin email"}
                                                    </p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <div className="flex flex-wrap gap-1 max-w-xs">
                                                {c.skills.slice(0, 3).map((skill, i) => (
                                                    <span
                                                        key={i}
                                                        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${selectedSkill.toLowerCase() === skill.toLowerCase()
                                                                ? "bg-primary/20 text-primary"
                                                                : "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                                                            }`}
                                                    >
                                                        {skill}
                                                    </span>
                                                ))}
                                                {c.skills.length > 3 && (
                                                    <span className="text-xs text-slate-400">+{c.skills.length - 3}</span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="py-4 px-6">
                                            <span className="text-sm text-slate-600 dark:text-slate-300">
                                                {c.experience}
                                            </span>
                                        </td>
                                        <td className="py-4 px-6">
                                            <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${c.status === "new"
                                                ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300"
                                                : c.status === "shortlisted"
                                                    ? "bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300"
                                                    : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                                                }`}>
                                                {c.status === "new" ? "Nuevo" : c.status === "reviewed" ? "Revisado" : c.status === "shortlisted" ? "Preseleccionado" : c.status}
                                            </span>
                                        </td>
                                        <td className="py-4 px-6 text-center">
                                            <div className="inline-flex items-center justify-center w-12 h-12 relative">
                                                <svg className="w-full h-full transform -rotate-90">
                                                    <circle
                                                        className="text-slate-200 dark:text-slate-700"
                                                        cx="24"
                                                        cy="24"
                                                        fill="transparent"
                                                        r="18"
                                                        stroke="currentColor"
                                                        strokeWidth="4"
                                                    ></circle>
                                                    <circle
                                                        className="text-emerald-500"
                                                        cx="24"
                                                        cy="24"
                                                        fill="transparent"
                                                        r="18"
                                                        stroke="currentColor"
                                                        strokeDasharray="113"
                                                        strokeDashoffset={113 - (113 * c.matchScore) / 100}
                                                        strokeLinecap="round"
                                                        strokeWidth="4"
                                                    ></circle>
                                                </svg>
                                                <span className="absolute text-[10px] font-bold text-slate-900 dark:text-white">
                                                    {c.matchScore}%
                                                </span>
                                            </div>
                                        </td>
                                        <td className="py-4 px-6 text-right">
                                            <Link
                                                href={`/candidates/${c.id}`}
                                                className="p-2 text-slate-400 hover:text-primary hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors inline-flex"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">
                                                    chevron_right
                                                </span>
                                            </Link>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <span className="text-sm text-slate-500 dark:text-slate-400">
                        Mostrando{" "}
                        <span className="font-medium text-slate-900 dark:text-white">
                            {filteredCandidates.length}
                        </span>{" "}
                        de {total} resultados
                    </span>
                </div>
            </div>
        </>
    );
};

export default CandidateList;
