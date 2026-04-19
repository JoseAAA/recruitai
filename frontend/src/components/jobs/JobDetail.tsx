"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { jobsApi, candidatesApi, searchApi, JobProfile, Candidate, MatchResult, InterviewQuestion } from "@/lib/api";
import { exportJobExcel } from "@/lib/export";
import { scoreColor } from "@/lib/utils";

// ── Recommendation config ────────────────────────────────────────────────────

const REC_DOT: Record<string, string> = {
    "Altamente recomendado": "bg-emerald-500",
    "Buena opción":          "bg-blue-500",
    "Considerar":            "bg-amber-500",
    "No recomendado":        "bg-slate-400",
};

const REC_BG: Record<string, string> = {
    "Altamente recomendado": "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/30",
    "Buena opción":          "bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-500/30",
    "Considerar":            "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/30",
    "No recomendado":        "bg-slate-100 dark:bg-slate-700/30 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-600",
};

function ScoreBadge({ value }: { value: number }) {
    const v = Math.round(value);
    const cls = v >= 75
        ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-500/30"
        : v >= 55
        ? "bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300 border-blue-300 dark:border-blue-500/30"
        : v >= 35
        ? "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-500/30"
        : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 border-slate-300 dark:border-slate-600";
    return (
        <span className={`shrink-0 text-xs font-bold px-1.5 py-0.5 rounded border tabular-nums ${cls}`}>
            {v}
        </span>
    );
}

// ── Interview question type labels ───────────────────────────────────────────

const QUESTION_TYPE: Record<string, { label: string; icon: string; color: string }> = {
    validar_logro:       { label: "Logro",     icon: "verified",     color: "text-emerald-500" },
    explorar_brecha:     { label: "Brecha",    icon: "help_outline", color: "text-amber-500" },
    validar_inferencia:  { label: "Inferencia",icon: "search",       color: "text-blue-500" },
};

// ── Ranking section ──────────────────────────────────────────────────────────

type SortCol = "overall_score" | "skills_score" | "experience_score" | "education_score";

function RankingSection({
    scores,
    loading,
    error,
    candidateCount,
    job,
    candidates,
    onRunMatch,
}: {
    scores: MatchResult[];
    loading: boolean;
    error: string | null;
    candidateCount: number;
    job: JobProfile;
    candidates: Candidate[];
    onRunMatch: () => void;
}) {
    const [sortBy, setSortBy] = useState<SortCol>("overall_score");
    const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
    const [minSkills, setMinSkills] = useState(0);
    const [minExp, setMinExp] = useState(0);
    const [minEdu, setMinEdu] = useState(0);
    const [expandedGuia, setExpandedGuia] = useState<Set<string>>(new Set());
    const [exporting, setExporting] = useState(false);

    function toggleSort(col: SortCol) {
        if (sortBy === col) setSortDir(d => d === "desc" ? "asc" : "desc");
        else { setSortBy(col); setSortDir("desc"); }
    }

    function toggleGuia(id: string) {
        setExpandedGuia(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    }

    function handleExport() {
        setExporting(true);
        try {
            exportJobExcel({ job, candidates, scores });
        } finally {
            setExporting(false);
        }
    }

    const filtered = scores.filter(s =>
        s.skills_score >= minSkills &&
        s.experience_score >= minExp &&
        s.education_score >= minEdu
    );

    const sorted = [...filtered].sort((a, b) => {
        const diff = (a[sortBy] ?? 0) - (b[sortBy] ?? 0);
        return sortDir === "desc" ? -diff : diff;
    });

    const lastRun = scores.map(s => s.scored_at).filter(Boolean).sort().at(-1);
    const lastRunLabel = lastRun
        ? new Intl.DateTimeFormat("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(lastRun))
        : null;

    // Lookup: candidateId → total_experience_years (from candidate list)
    const candidateExpMap = new Map<string, number>();
    for (const c of candidates) candidateExpMap.set(c.id, c.total_experience_years ?? 0);

    // Build weight labels from job.scoring_config (or defaults)
    const DEFAULT_WEIGHTS: Record<string, number> = { skills: 0.40, experience: 0.35, education: 0.25 };
    const weightMap: Record<string, number> = {};
    for (const dim of (job.scoring_config ?? [])) {
        weightMap[dim.dimension] = dim.weight;
    }
    const skillsW  = Math.round((weightMap.skills    ?? DEFAULT_WEIGHTS.skills)    * 100);
    const expW     = Math.round((weightMap.experience ?? DEFAULT_WEIGHTS.experience) * 100);
    const eduW     = Math.round((weightMap.education  ?? DEFAULT_WEIGHTS.education)  * 100);

    return (
        <div className="space-y-4">
            {/* Toolbar */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-3">
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
                        {lastRunLabel && !loading && (
                            <span className="text-xs text-slate-400">Actualizado: {lastRunLabel}</span>
                        )}
                    </div>

                    {scores.length > 0 && (
                        <button
                            onClick={handleExport}
                            disabled={exporting}
                            className="flex items-center gap-2 px-3.5 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                        >
                            <span className="material-symbols-outlined text-[18px]">download</span>
                            Exportar Excel
                        </button>
                    )}
                </div>

                {/* Dimension filters */}
                {scores.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                        <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3">Filtrar por puntaje mínimo</p>
                        <div className="grid grid-cols-3 gap-4">
                            {[
                                { label: "Skills", val: minSkills, set: setMinSkills },
                                { label: "Experiencia", val: minExp, set: setMinExp },
                                { label: "Educación", val: minEdu, set: setMinEdu },
                            ].map(({ label, val, set }) => (
                                <div key={label} className="flex items-center gap-2">
                                    <span className="text-xs text-slate-500 w-20 flex-shrink-0">{label} ≥</span>
                                    <input
                                        type="range" min={0} max={100} step={5} value={val}
                                        onChange={e => set(Number(e.target.value))}
                                        className="flex-1 accent-primary h-1.5"
                                    />
                                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 w-8 text-right">{val}%</span>
                                </div>
                            ))}
                        </div>
                        {(minSkills > 0 || minExp > 0 || minEdu > 0) && (
                            <div className="flex items-center justify-between mt-2">
                                <span className="text-xs text-slate-400">{sorted.length} de {scores.length} candidatos</span>
                                <button
                                    onClick={() => { setMinSkills(0); setMinExp(0); setMinEdu(0); }}
                                    className="text-xs text-primary hover:underline"
                                >
                                    Limpiar filtros
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {error && (
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 text-rose-700 dark:text-rose-400 text-sm">
                    <span className="material-symbols-outlined text-[18px] flex-shrink-0">error</span>
                    {error}
                </div>
            )}

            {/* List */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                {loading ? (
                    <div className="py-16 flex flex-col items-center gap-4 text-slate-500">
                        <span className="material-symbols-outlined text-[40px] text-primary animate-spin">sync</span>
                        <p className="text-sm">Evaluando {candidateCount} candidato{candidateCount !== 1 ? "s" : ""} con IA...</p>
                        <p className="text-xs text-slate-400">~30 segundos por candidato en Ollama local</p>
                    </div>
                ) : sorted.length === 0 ? (
                    <div className="py-16 text-center">
                        <span className="material-symbols-outlined text-[48px] text-slate-300 dark:text-slate-600 block mb-3">leaderboard</span>
                        <p className="text-slate-500 text-sm">
                            {candidateCount === 0
                                ? "Importa CVs primero."
                                : scores.length === 0
                                ? "Usa \"Analizar con IA\" para generar el ranking."
                                : "Ningún candidato cumple los filtros actuales."}
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Sort header */}
                        <div className="grid grid-cols-[1.5rem_1fr_5rem_5rem_5rem_5rem] px-5 py-2.5 border-b border-slate-100 dark:border-slate-700/50 bg-slate-50 dark:bg-slate-800/80 gap-2">
                            <span />
                            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Candidato</span>
                            {([
                                { col: "overall_score"    as SortCol, label: "Total",  sub: "" },
                                { col: "skills_score"     as SortCol, label: "Skills", sub: `${skillsW}%` },
                                { col: "experience_score" as SortCol, label: "Exp.",   sub: `${expW}%` },
                                { col: "education_score"  as SortCol, label: "Edu.",   sub: `${eduW}%` },
                            ]).map(({ col, label, sub }) => (
                                <button key={col} onClick={() => toggleSort(col)}
                                    className={`flex flex-col items-center gap-0 text-[11px] font-bold uppercase tracking-wider transition-colors ${sortBy === col ? "text-primary" : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"}`}
                                >
                                    <span className="flex items-center gap-0.5">
                                        {label}
                                        {sortBy === col && <span className="material-symbols-outlined text-[12px]">{sortDir === "desc" ? "arrow_downward" : "arrow_upward"}</span>}
                                    </span>
                                    {sub && <span className="text-[10px] font-normal normal-case tracking-normal text-slate-400 opacity-70">{sub}</span>}
                                </button>
                            ))}
                        </div>

                        <div className="divide-y divide-slate-100 dark:divide-slate-700/40">
                            {sorted.map((s, i) => {
                                const initials = s.full_name.split(" ").map(n => n[0]).join("").slice(0, 2).toUpperCase();
                                const recBg = REC_BG[s.recommendation] ?? REC_BG["Considerar"];
                                const dotColor = REC_DOT[s.recommendation] ?? "bg-slate-400";
                                const guiaOpen = expandedGuia.has(s.candidate_id);
                                const hasGuia = (s.guia_entrevista?.length ?? 0) > 0;

                                return (
                                    <div key={s.candidate_id} className="px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/20 transition-colors">
                                        {/* Row summary */}
                                        <div className="grid grid-cols-[1.5rem_1fr_5rem_5rem_5rem_5rem] items-center gap-2 mb-3">
                                            <span className="text-xs font-bold text-slate-400">#{i + 1}</span>

                                            <div className="flex items-center gap-2.5 min-w-0">
                                                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                                                    {initials}
                                                </div>
                                                <div className="min-w-0">
                                                    <Link href={`/candidates/${s.candidate_id}`}
                                                        className="text-sm font-semibold text-slate-900 dark:text-white hover:text-primary transition-colors truncate block leading-tight">
                                                        {s.full_name}
                                                    </Link>
                                                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                                                        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-full border ${recBg}`}>
                                                            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
                                                            {s.recommendation}
                                                        </span>
                                                        {/* Experience insight: relevant vs total */}
                                                        {(() => {
                                                            const totalYears = candidateExpMap.get(s.candidate_id) ?? 0;
                                                            const relYears = s.relevant_experience_years;
                                                            if (relYears != null && totalYears > 0) {
                                                                return (
                                                                    <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                                                                        <span className="material-symbols-outlined text-[12px] text-primary">work_history</span>
                                                                        <span className="font-bold text-primary">{relYears}a</span>
                                                                        <span className="text-slate-300 dark:text-slate-600">/</span>
                                                                        <span>{totalYears}a</span>
                                                                        <span className="text-slate-400">relevante/total</span>
                                                                    </span>
                                                                );
                                                            }
                                                            if (totalYears > 0) {
                                                                return (
                                                                    <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                                                                        <span className="material-symbols-outlined text-[12px]">work_history</span>
                                                                        {totalYears}a exp.
                                                                    </span>
                                                                );
                                                            }
                                                            return null;
                                                        })()}
                                                    </div>
                                                </div>
                                            </div>

                                            {([s.overall_score, s.skills_score, s.experience_score, s.education_score] as const).map((val, ci) => {
                                                const v = Math.round(val);
                                                const { text } = scoreColor(v);
                                                const cols = ["overall_score","skills_score","experience_score","education_score"] as SortCol[];
                                                return (
                                                    <div key={ci} className="flex justify-center">
                                                        <span className={`font-black text-lg tabular-nums ${text} ${sortBy === cols[ci] ? "underline decoration-dotted underline-offset-2" : ""}`}>{v}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>

                                        {/* Explanation — collapsed by default for density */}
                                        {s.explanation && (
                                            <p className="ml-11 text-xs text-slate-500 dark:text-slate-400 leading-relaxed mb-2 line-clamp-2">{s.explanation}</p>
                                        )}

                                        {/* Missing skills */}
                                        {s.missing_skills.length > 0 && (
                                            <div className="ml-11 flex flex-wrap gap-1 mb-2">
                                                <span className="text-[11px] text-slate-400 flex-shrink-0 self-center">Faltantes:</span>
                                                {s.missing_skills.map((sk, ki) => (
                                                    <span key={ki} className="px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400 text-[11px] font-medium border border-rose-200 dark:border-rose-500/20">{sk}</span>
                                                ))}
                                            </div>
                                        )}

                                        {/* Interview guide toggle */}
                                        {hasGuia && (
                                            <div className="ml-11">
                                                <button
                                                    onClick={() => toggleGuia(s.candidate_id)}
                                                    className="flex items-center gap-1.5 text-[11px] font-semibold text-primary hover:text-blue-600 transition-colors py-1"
                                                >
                                                    <span className="material-symbols-outlined text-[14px]">
                                                        {guiaOpen ? "expand_less" : "expand_more"}
                                                    </span>
                                                    {guiaOpen ? "Ocultar" : "Ver"} preguntas de entrevista
                                                </button>
                                                {guiaOpen && (
                                                    <div className="mt-1.5 space-y-1.5 pl-1 border-l-2 border-primary/20">
                                                        {s.guia_entrevista!.map((q, qi) => {
                                                            const meta = QUESTION_TYPE[q.tipo] ?? QUESTION_TYPE["validar_logro"];
                                                            return (
                                                                <div key={qi} className="flex items-start gap-2">
                                                                    <span className={`material-symbols-outlined text-[14px] flex-shrink-0 mt-0.5 ${meta.color}`}>{meta.icon}</span>
                                                                    <div>
                                                                        <span className="text-[10px] font-bold text-slate-400 uppercase">{meta.label}</span>
                                                                        <p className="text-xs text-slate-700 dark:text-slate-300">{q.pregunta}</p>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

// ── Pipeline Tab ─────────────────────────────────────────────────────────────

const PIPELINE_STAGES = [
    { id: "new",       label: "Nuevos",     description: "Pendientes de revisión",  icon: "inbox",        headerBg: "bg-blue-50 dark:bg-blue-500/10 border-blue-200 dark:border-blue-500/30",         iconColor: "text-blue-500",    badge: "bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300",         statuses: ["new", "screening", "shortlisted"] },
    { id: "interview", label: "Entrevista", description: "En proceso de selección", icon: "groups",       headerBg: "bg-violet-50 dark:bg-violet-500/10 border-violet-200 dark:border-violet-500/30", iconColor: "text-violet-500",  badge: "bg-violet-100 dark:bg-violet-500/20 text-violet-700 dark:text-violet-300", statuses: ["interview"] },
    { id: "hired",     label: "Contratado", description: "Seleccionado / Oferta",   icon: "check_circle", headerBg: "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/30", iconColor: "text-emerald-500", badge: "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300", statuses: ["hired", "offer"] },
    { id: "rejected",  label: "Descartado", description: "No avanza",               icon: "cancel",       headerBg: "bg-slate-100 dark:bg-slate-700/30 border-slate-200 dark:border-slate-600",         iconColor: "text-slate-400",   badge: "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400",         statuses: ["rejected"] },
] as const;

const MOVE_STATUS: Record<string, string> = { new: "new", interview: "interview", hired: "hired", rejected: "rejected" };
const COLUMN_PAGE_SIZE = 5;

interface PipelineTabProps {
    candidates: Candidate[];
    scoreMap: Record<string, number>;
    isAdmin: boolean;
    deleteError: string | null;
    deletingId: string | null;
    updatingStatusId: string | null;
    onStatusChange: (id: string, status: string) => void;
    onDeleteRequest: (id: string) => void;
    onDeleteConfirm: (id: string) => void;
    onDeleteCancel: () => void;
    onImportCVs: () => void;
}

function PipelineTab({ candidates, scoreMap, isAdmin, deleteError, deletingId, updatingStatusId, onStatusChange, onDeleteRequest, onDeleteConfirm, onDeleteCancel, onImportCVs }: PipelineTabProps) {
    const [search, setSearch] = useState("");
    const [sortMode, setSortMode] = useState<"score" | "date" | "name">("score");
    const [filterMode, setFilterMode] = useState<"all" | "scored" | "unscored">("all");
    const [expandedCols, setExpandedCols] = useState<Set<string>>(new Set());
    const [draggingId, setDraggingId] = useState<string | null>(null);
    const [draggingFromCol, setDraggingFromCol] = useState<string | null>(null);
    const [dragOverCol, setDragOverCol] = useState<string | null>(null);

    function toggleCol(colId: string) {
        setExpandedCols(prev => {
            const next = new Set(prev);
            next.has(colId) ? next.delete(colId) : next.add(colId);
            return next;
        });
    }

    // Apply search + filter
    const filtered = candidates.filter(c => {
        if (search && !c.full_name.toLowerCase().includes(search.toLowerCase())) return false;
        if (filterMode === "scored" && scoreMap[c.id] == null) return false;
        if (filterMode === "unscored" && scoreMap[c.id] != null) return false;
        return true;
    });

    // Sort within each stage
    function sortCards(cards: Candidate[]): Candidate[] {
        return [...cards].sort((a, b) => {
            if (sortMode === "score") {
                const sa = scoreMap[a.id] ?? -1;
                const sb = scoreMap[b.id] ?? -1;
                return sb - sa;
            }
            if (sortMode === "name") return a.full_name.localeCompare(b.full_name);
            return 0;
        });
    }

    // Group by stage
    const grouped: Record<string, Candidate[]> = { new: [], interview: [], hired: [], rejected: [] };
    filtered.forEach(c => {
        const stage = PIPELINE_STAGES.find(s => (s.statuses as unknown as string[]).includes(c.status));
        if (stage) grouped[stage.id].push(c);
    });

    if (candidates.length === 0) {
        return (
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl py-16 text-center">
                <span className="material-symbols-outlined text-[48px] text-slate-300 dark:text-slate-600 block mb-3">upload_file</span>
                <p className="text-slate-500 mb-4">Aún no hay CVs en esta convocatoria</p>
                <button onClick={onImportCVs} className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600">
                    <span className="material-symbols-outlined text-[18px]">upload_file</span>
                    Importar CVs
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {deleteError && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400">{deleteError}</div>
            )}

            {/* Controls */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="flex items-center gap-2 flex-1 min-w-[200px] bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2">
                    <span className="material-symbols-outlined text-[18px] text-slate-400">search</span>
                    <input
                        type="text"
                        placeholder="Buscar por nombre..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        className="flex-1 bg-transparent text-sm text-slate-700 dark:text-slate-200 placeholder-slate-400 outline-none"
                    />
                    {search && (
                        <button onClick={() => setSearch("")} className="text-slate-400 hover:text-slate-600">
                            <span className="material-symbols-outlined text-[16px]">close</span>
                        </button>
                    )}
                </div>

                {/* Sort */}
                <div className="flex items-center gap-1.5">
                    <span className="text-xs text-slate-400">Ordenar:</span>
                    {[
                        { id: "score", label: "Puntuación" },
                        { id: "name",  label: "Nombre" },
                        { id: "date",  label: "Fecha" },
                    ].map(opt => (
                        <button key={opt.id}
                            onClick={() => setSortMode(opt.id as any)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${sortMode === opt.id ? "bg-primary text-white" : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"}`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>

                {/* Filter */}
                <div className="flex items-center gap-1.5">
                    {[
                        { id: "all",     label: "Todos" },
                        { id: "scored",  label: "Con score" },
                        { id: "unscored",label: "Sin score" },
                    ].map(opt => (
                        <button key={opt.id}
                            onClick={() => setFilterMode(opt.id as any)}
                            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${filterMode === opt.id ? "bg-slate-700 dark:bg-slate-200 text-white dark:text-slate-900" : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"}`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>

                {filtered.length !== candidates.length && (
                    <span className="text-xs text-slate-400">{filtered.length} de {candidates.length}</span>
                )}
            </div>

            {/* Kanban columns */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {PIPELINE_STAGES.map(stage => {
                    const allCards = sortCards(grouped[stage.id]);
                    const isExpanded = expandedCols.has(stage.id);
                    const visibleCards = isExpanded ? allCards : allCards.slice(0, COLUMN_PAGE_SIZE);
                    const hiddenCount = allCards.length - COLUMN_PAGE_SIZE;
                    const isDropTarget = dragOverCol === stage.id && draggingFromCol !== stage.id;

                    return (
                        <div key={stage.id}
                            className={`flex flex-col rounded-xl border transition-all ${isDropTarget ? "border-primary ring-2 ring-primary/30 scale-[1.01]" : stage.headerBg}`}
                            onDragOver={e => { e.preventDefault(); if (draggingFromCol !== stage.id) setDragOverCol(stage.id); }}
                            onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverCol(null); }}
                            onDrop={e => {
                                e.preventDefault();
                                const id = e.dataTransfer.getData("candidateId");
                                if (id && draggingFromCol !== stage.id) onStatusChange(id, MOVE_STATUS[stage.id]);
                                setDragOverCol(null);
                                setDraggingId(null);
                                setDraggingFromCol(null);
                            }}
                        >
                            {/* Column header */}
                            <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-xl border-b ${isDropTarget ? "border-primary/30" : "border-inherit"}`}>
                                <div className="flex items-center gap-2">
                                    <span className={`material-symbols-outlined text-[18px] ${stage.iconColor}`}>{stage.icon}</span>
                                    <div>
                                        <p className="text-sm font-bold text-slate-800 dark:text-slate-100 leading-none">{stage.label}</p>
                                        <p className="text-[10px] text-slate-400 mt-0.5">{stage.description}</p>
                                    </div>
                                </div>
                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${stage.badge}`}>{allCards.length}</span>
                            </div>

                            {/* Cards */}
                            <div className={`flex-1 p-2 space-y-2 min-h-[80px] rounded-b-xl transition-colors ${isDropTarget ? "bg-primary/5 dark:bg-primary/10" : "bg-white dark:bg-slate-800/30"}`}>
                                {allCards.length === 0 ? (
                                    <div className={`flex items-center justify-center h-16 rounded-lg border-2 border-dashed transition-colors ${isDropTarget ? "border-primary/40" : "border-slate-200 dark:border-slate-700/50"}`}>
                                        <p className="text-[11px] text-slate-400">{isDropTarget ? "Soltar aquí" : "Sin candidatos"}</p>
                                    </div>
                                ) : (
                                    <>
                                        {visibleCards.map(c => {
                                            const score = scoreMap[c.id];
                                            const initials = c.full_name.split(" ").filter(Boolean).slice(0, 2).map(n => n[0]).join("").toUpperCase();
                                            const isDeleting = deletingId === c.id;
                                            const isDragging = draggingId === c.id;

                                            return (
                                                <div key={c.id}
                                                    draggable={!isDeleting}
                                                    onDragStart={e => {
                                                        e.dataTransfer.setData("candidateId", c.id);
                                                        e.dataTransfer.effectAllowed = "move";
                                                        setDraggingId(c.id);
                                                        setDraggingFromCol(stage.id);
                                                    }}
                                                    onDragEnd={() => { setDraggingId(null); setDraggingFromCol(null); setDragOverCol(null); }}
                                                    className={`bg-white dark:bg-slate-800 border rounded-xl p-3 shadow-sm transition-all select-none ${
                                                        isDragging ? "opacity-40 scale-95" :
                                                        isDeleting ? "border-red-300 dark:border-red-500/40 bg-red-50 dark:bg-red-900/10" :
                                                        "border-slate-200 dark:border-slate-700 hover:shadow-md hover:border-primary/30 cursor-grab active:cursor-grabbing"
                                                    }`}
                                                >
                                                    <div className="flex items-start gap-2">
                                                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5">{initials}</div>
                                                        <div className="flex-1 min-w-0">
                                                            <Link href={`/candidates/${c.id}`} className="text-sm font-semibold text-slate-900 dark:text-white hover:text-primary truncate block leading-tight">{c.full_name}</Link>
                                                            {c.total_experience_years > 0 && (
                                                                <p className="text-[11px] text-slate-400 mt-0.5">{c.total_experience_years} año{c.total_experience_years !== 1 ? "s" : ""} exp.</p>
                                                            )}
                                                            {c.skills.length > 0 && (
                                                                <div className="flex flex-wrap gap-1 mt-1.5">
                                                                    {c.skills.slice(0, 2).map((sk, i) => (
                                                                        <span key={i} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">{sk}</span>
                                                                    ))}
                                                                    {c.skills.length > 2 && <span className="text-[10px] text-slate-400">+{c.skills.length - 2}</span>}
                                                                </div>
                                                            )}
                                                        </div>
                                                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                                                            {score != null && <ScoreBadge value={score} />}
                                                            {isAdmin && !isDeleting && (
                                                                <button
                                                                    onClick={e => { e.stopPropagation(); onDeleteRequest(c.id); }}
                                                                    className="p-0.5 rounded text-slate-300 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                                                                >
                                                                    <span className="material-symbols-outlined text-[14px]">delete</span>
                                                                </button>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {isDeleting && (
                                                        <div className="flex items-center gap-1.5 mt-2 pt-2 border-t border-red-200 dark:border-red-500/30">
                                                            <span className="text-[11px] text-red-600 dark:text-red-400 font-medium flex-1">¿Eliminar?</span>
                                                            <button onClick={() => onDeleteConfirm(c.id)} className="px-2 py-0.5 rounded bg-red-500 text-white text-[11px] font-semibold">Sí</button>
                                                            <button onClick={onDeleteCancel} className="px-2 py-0.5 rounded border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-[11px]">No</button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}

                                        {/* Ver más / Ver menos */}
                                        {allCards.length > COLUMN_PAGE_SIZE && (
                                            <button
                                                onClick={() => toggleCol(stage.id)}
                                                className="w-full py-1.5 text-[11px] font-semibold text-primary hover:text-blue-600 transition-colors flex items-center justify-center gap-1"
                                            >
                                                <span className="material-symbols-outlined text-[14px]">{isExpanded ? "expand_less" : "expand_more"}</span>
                                                {isExpanded ? "Ver menos" : `Ver ${hiddenCount} más`}
                                            </button>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    );
                })}
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
                    <button onClick={() => { onClose(); setOpen(false); }}
                        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined text-[18px]">{status === "active" ? "lock" : "lock_open"}</span>
                        {status === "active" ? "Cerrar vacante" : "Reabrir vacante"}
                    </button>
                    <button onClick={() => { onDelete(); setOpen(false); }}
                        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                        Eliminar vacante
                    </button>
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

    // Pipeline is the default tab — HR comes here to check who's where
    const [activeTab, setActiveTab] = useState<"pipeline" | "ranking" | "requisitos">("pipeline");

    const [scores, setScores] = useState<MatchResult[]>([]);
    const [matchLoading, setMatchLoading] = useState(false);
    const [matchError, setMatchError] = useState<string | null>(null);

    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [showDeleteJobConfirm, setShowDeleteJobConfirm] = useState(false);
    const [deletingJob, setDeletingJob] = useState(false);
    const [updatingStatusId, setUpdatingStatusId] = useState<string | null>(null);

    useEffect(() => { loadAll(); }, [jobId]);

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
        } catch {
            setError("No se pudo cargar la convocatoria");
        } finally {
            setLoading(false);
        }
    }

    async function runMatch() {
        setMatchLoading(true);
        setMatchError(null);
        try {
            const res = await searchApi.match(jobId, 20);
            setScores(res.data.matches || []);
        } catch (e: any) {
            setMatchError(e.response?.data?.detail || "Error al generar el análisis. Intenta de nuevo.");
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
            setDeleteError(e.response?.data?.detail || "Error al eliminar");
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
    const scoreMap = Object.fromEntries(scores.map(s => [s.candidate_id, s.overall_score]));

    return (
        <div className="space-y-5 max-w-5xl">

            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-slate-500">
                <Link href="/jobs" className="hover:text-primary transition-colors flex items-center gap-1">
                    <span className="material-symbols-outlined text-[16px]">arrow_back</span>
                    Perfiles de Puesto
                </Link>
                <span>/</span>
                <span className="text-slate-700 dark:text-slate-200 font-medium truncate">{job.title}</span>
            </div>

            {/* Header */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl p-6">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 flex-wrap mb-1">
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{job.title}</h1>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${job.status === "active" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" : "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400"}`}>
                                {job.status === "active" ? "Activo" : job.status === "closed" ? "Cerrado" : job.status}
                            </span>
                        </div>
                        {job.department && <p className="text-slate-500 text-sm">{job.department}</p>}

                        <div className="flex flex-wrap gap-2 mt-3">
                            {[
                                job.seniority_level   && { icon: "grade",        label: job.seniority_level },
                                job.work_modality      && { icon: "location_on",  label: job.work_modality },
                                job.industry           && { icon: "business",     label: job.industry },
                                job.min_experience_years > 0 && { icon: "work_history", label: `${job.min_experience_years}+ años` },
                            ].filter(Boolean).map((tag: any) => (
                                <span key={tag.icon} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-700/60 text-slate-600 dark:text-slate-300 text-xs font-medium border border-slate-200 dark:border-slate-600">
                                    <span className="material-symbols-outlined text-[13px]">{tag.icon}</span>{tag.label}
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2 flex-shrink-0">
                        <button
                            onClick={() => router.push(`/data?job_id=${job.id}`)}
                            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-blue-600 transition-colors shadow-sm"
                        >
                            <span className="material-symbols-outlined text-[18px]">upload_file</span>
                            Importar CVs
                        </button>
                        <MoreMenu status={job.status} onClose={handleCloseJob} onDelete={() => setShowDeleteJobConfirm(true)} />
                    </div>
                </div>

                {/* Stats bar */}
                <div className="mt-5 grid grid-cols-3 gap-3">
                    {[
                        { icon: "group",      value: candidates.length,                                      label: "CVs recibidos" },
                        { icon: "groups",     value: candidates.filter(c => c.status === "interview").length, label: "En entrevista" },
                        { icon: "psychology", value: scores.length,                                           label: "Con score IA" },
                    ].map(({ icon, value, label }) => (
                        <div key={label} className="flex items-center gap-2 py-2.5 px-3.5 rounded-xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200 dark:border-slate-600">
                            <span className="material-symbols-outlined text-[18px] text-slate-400">{icon}</span>
                            <span className="text-lg font-black text-slate-800 dark:text-white">{value}</span>
                            <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Tab navigation — Pipeline first */}
            <div className="flex items-center gap-1 bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-1.5 shadow-sm">
                {([
                    { id: "pipeline",   label: `Pipeline (${candidates.length})`, icon: "view_kanban" },
                    { id: "ranking",    label: `Ranking IA (${scores.length})`,   icon: "psychology" },
                    { id: "requisitos", label: "Requisitos",                       icon: "description" },
                ] as const).map(tab => (
                    <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${activeTab === tab.id ? "bg-primary text-white shadow-sm shadow-primary/20" : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-700 dark:hover:text-slate-200"}`}
                    >
                        <span className="material-symbols-outlined text-[18px]">{tab.icon}</span>
                        <span className="hidden sm:inline">{tab.label}</span>
                    </button>
                ))}
            </div>

            {/* Tab: Pipeline */}
            {activeTab === "pipeline" && (
                <PipelineTab
                    candidates={candidates}
                    scoreMap={scoreMap}
                    isAdmin={isAdmin}
                    deleteError={deleteError}
                    deletingId={deletingId}
                    updatingStatusId={updatingStatusId}
                    onStatusChange={handleStatusChange}
                    onDeleteRequest={(id) => { setDeletingId(id); setDeleteError(null); }}
                    onDeleteConfirm={handleDeleteCandidate}
                    onDeleteCancel={() => setDeletingId(null)}
                    onImportCVs={() => router.push(`/data?job_id=${job.id}`)}
                />
            )}

            {/* Tab: Ranking IA */}
            {activeTab === "ranking" && (
                <RankingSection
                    scores={scores}
                    loading={matchLoading}
                    error={matchError}
                    candidateCount={candidates.length}
                    job={job}
                    candidates={candidates}
                    onRunMatch={runMatch}
                />
            )}

            {/* Tab: Requisitos */}
            {activeTab === "requisitos" && (
                <div className="space-y-5">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                        {(job.description || (job.key_objectives?.length ?? 0) > 0 || (job.responsibilities?.length ?? 0) > 0) && (
                            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 space-y-5">
                                {job.description && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">info</span>Descripción del Puesto
                                        </h3>
                                        <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{job.description}</p>
                                    </div>
                                )}
                                {(job.responsibilities?.length ?? 0) > 0 && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">checklist</span>Responsabilidades
                                        </h3>
                                        <ul className="space-y-1.5">
                                            {job.responsibilities!.map((r, i) => (
                                                <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                                                    <span className="w-1 h-1 rounded-full bg-primary flex-shrink-0 mt-2"></span>{r}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {(job.key_objectives?.length ?? 0) > 0 && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">flag</span>Objetivos Clave
                                        </h3>
                                        <ul className="space-y-1.5">
                                            {job.key_objectives!.map((o, i) => (
                                                <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                                                    <span className="text-emerald-500 font-bold mt-0.5 flex-shrink-0">✓</span>{o}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

                        {((job.required_skills?.length ?? 0) > 0 || (job.preferred_skills?.length ?? 0) > 0) && (
                            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 space-y-5">
                                {(job.required_skills?.length ?? 0) > 0 && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">psychology</span>
                                            Habilidades Requeridas
                                            <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400 font-bold">Impacto en scoring</span>
                                        </h3>
                                        <div className="flex flex-wrap gap-1.5">
                                            {job.required_skills.map((s, i) => (
                                                <span key={i} className="px-2.5 py-1 rounded-full bg-primary/10 text-primary dark:text-blue-300 text-xs font-semibold border border-primary/20">{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {(job.preferred_skills?.length ?? 0) > 0 && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">star</span>Habilidades Deseables
                                        </h3>
                                        <div className="flex flex-wrap gap-1.5">
                                            {job.preferred_skills.map((s, i) => (
                                                <span key={i} className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium">{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {(job.required_languages?.length ?? 0) > 0 && (
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                            <span className="material-symbols-outlined text-[14px]">language</span>Idiomas Requeridos
                                        </h3>
                                        <div className="flex flex-wrap gap-1.5">
                                            {job.required_languages!.map((lang: any, i) => (
                                                <span key={i} className="px-2.5 py-1 rounded-full bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 text-xs font-medium border border-teal-200 dark:border-teal-800">
                                                    {lang.idioma} · {lang.nivel}{lang.obligatorio ? " ✱" : ""}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Delete job modal */}
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
                            <button onClick={() => setShowDeleteJobConfirm(false)}
                                className="flex-1 px-4 py-2 rounded-lg border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                                Cancelar
                            </button>
                            <button onClick={handleDeleteJob} disabled={deletingJob}
                                className="flex-1 px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-semibold transition-colors disabled:opacity-60">
                                {deletingJob ? "Eliminando..." : "Eliminar"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default JobDetail;
