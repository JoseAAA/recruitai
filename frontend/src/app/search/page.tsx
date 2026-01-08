"use client";

import { useState } from "react";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { cn } from "@/lib/utils";

interface SearchResult {
    candidateId: string;
    fullName: string;
    score: number;
    skills: string[];
    experienceYears: number;
}

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [isSearching, setIsSearching] = useState(false);
    const [searchType, setSearchType] = useState<"semantic" | "hybrid">("hybrid");
    const [results, setResults] = useState<SearchResult[]>([]);

    const handleSearch = async () => {
        if (!query.trim()) return;

        setIsSearching(true);
        await new Promise((r) => setTimeout(r, 1000));

        setResults([
            {
                candidateId: "1",
                fullName: "Alex Johnson",
                score: 0.94,
                skills: ["Python", "FastAPI", "AWS", "Docker"],
                experienceYears: 8,
            },
            {
                candidateId: "2",
                fullName: "María García",
                score: 0.87,
                skills: ["Python", "Django", "PostgreSQL"],
                experienceYears: 6,
            },
            {
                candidateId: "3",
                fullName: "Chen Wei",
                score: 0.82,
                skills: ["Go", "Python", "Kubernetes"],
                experienceYears: 10,
            },
        ]);

        setIsSearching(false);
    };

    const getScoreColor = (score: number) => {
        const s = score * 100;
        if (s >= 80) return "text-emerald-400 bg-emerald-500/20 border-emerald-500/30";
        if (s >= 60) return "text-green-400 bg-green-500/20 border-green-500/30";
        if (s >= 40) return "text-amber-400 bg-amber-500/20 border-amber-500/30";
        return "text-rose-400 bg-rose-500/20 border-rose-500/30";
    };

    return (
        <DashboardLayout>
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-white">Búsqueda Semántica</h1>
                    <p className="text-slate-400">
                        Encuentra candidatos usando consultas en lenguaje natural
                    </p>
                </div>

                {/* Search Bar */}
                <div className="space-y-4">
                    <div className="flex gap-2">
                        <div className="relative flex-1">
                            <span className="absolute left-4 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                                search
                            </span>
                            <input
                                type="text"
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                                placeholder="ej., Desarrollador Python con experiencia en AWS y microservicios"
                                className="w-full pl-12 pr-4 py-3 rounded-xl bg-[#1e293b] border border-[#334155] focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all text-white placeholder-slate-500"
                            />
                        </div>
                        <select
                            value={searchType}
                            onChange={(e) => setSearchType(e.target.value as any)}
                            className="px-4 py-3 rounded-xl bg-[#1e293b] border border-[#334155] focus:outline-none focus:border-[#135bec] text-white"
                        >
                            <option value="hybrid">Híbrida (RRF)</option>
                            <option value="semantic">Solo Semántica</option>
                        </select>
                        <button
                            onClick={handleSearch}
                            disabled={isSearching || !query.trim()}
                            className="px-6 py-3 rounded-xl bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                        >
                            {isSearching ? (
                                <span className="material-symbols-outlined animate-spin">progress_activity</span>
                            ) : (
                                <span className="material-symbols-outlined">search</span>
                            )}
                            Buscar
                        </button>
                    </div>
                </div>

                {/* Results */}
                {results.length > 0 && (
                    <div className="space-y-3">
                        <h3 className="text-sm font-medium text-slate-400">
                            {results.length} resultados encontrados
                        </h3>
                        {results.map((result) => (
                            <div
                                key={result.candidateId}
                                className="flex items-center gap-4 p-4 rounded-xl bg-[#1e293b] border border-[#334155] hover:border-[#135bec]/30 transition-all cursor-pointer"
                            >
                                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#135bec]/50 to-purple-500/50 flex items-center justify-center flex-shrink-0">
                                    <span className="text-lg font-medium text-white">
                                        {result.fullName.split(" ").map((n) => n[0]).join("")}
                                    </span>
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h4 className="font-semibold text-white">{result.fullName}</h4>
                                    <p className="text-sm text-slate-400">
                                        {result.experienceYears} años de experiencia
                                    </p>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {result.skills.slice(0, 4).map((skill) => (
                                            <span
                                                key={skill}
                                                className="px-2 py-0.5 rounded text-xs bg-slate-700 text-slate-300"
                                            >
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                <div
                                    className={cn(
                                        "w-14 h-14 rounded-full border flex items-center justify-center text-xl font-bold",
                                        getScoreColor(result.score)
                                    )}
                                >
                                    {Math.round(result.score * 100)}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </DashboardLayout>
    );
}
