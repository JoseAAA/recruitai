"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import Link from "next/link";
import { candidatesApi, jobsApi, Candidate as ApiCandidate, JobProfile } from "@/lib/api";
import { exportCandidatesCsv } from "@/lib/export";

// ── Types ────────────────────────────────────────────────────────────────────

interface CandidateRow extends ApiCandidate {
    match_score?: number;
    recommendation?: string;
    missing_skills?: string[];
    bonus_skills?: string[];
    job_title?: string;
}

// ── Config — ALL Tailwind classes must be full static strings ─────────────────

const STATUS_CFG: Record<string, { label: string; dot: string; pill: string; activePill: string }> = {
    new:         { label: "Nuevo",      dot: "bg-blue-400",    pill: "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700",    activePill: "bg-blue-500 text-white border-blue-600" },
    screening:   { label: "Revisión",   dot: "bg-amber-400",   pill: "bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-700",  activePill: "bg-amber-500 text-white border-amber-600" },
    shortlisted: { label: "Preselecto", dot: "bg-indigo-400",  pill: "bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700", activePill: "bg-indigo-500 text-white border-indigo-600" },
    interview:   { label: "Entrevista", dot: "bg-violet-400",  pill: "bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border border-violet-200 dark:border-violet-700", activePill: "bg-violet-500 text-white border-violet-600" },
    offer:       { label: "Oferta",     dot: "bg-orange-400",  pill: "bg-orange-50 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border border-orange-200 dark:border-orange-700", activePill: "bg-orange-500 text-white border-orange-600" },
    hired:       { label: "Contratado", dot: "bg-emerald-400", pill: "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-700", activePill: "bg-emerald-500 text-white border-emerald-600" },
    rejected:    { label: "Descartado", dot: "bg-slate-400",   pill: "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600",       activePill: "bg-slate-500 text-white border-slate-600" },
};
const ALL_STATUSES = ["new", "screening", "shortlisted", "interview", "offer", "hired", "rejected"];

// Deterministic, solid avatar background colors — white text always readable
const AVATAR_BG = [
    "bg-blue-500", "bg-violet-500", "bg-emerald-500", "bg-rose-500",
    "bg-amber-500", "bg-cyan-600", "bg-indigo-500", "bg-pink-500", "bg-teal-500",
];
const avatarBg = (name: string) =>
    AVATAR_BG[(name.charCodeAt(0) + (name.charCodeAt(1) || 0)) % AVATAR_BG.length];

const initials = (name: string) =>
    name.split(" ").filter(Boolean).slice(0, 2).map(n => n[0]).join("").toUpperCase();

function scoreLabel(score: number): string {
    if (score >= 80) return "Excelente";
    if (score >= 65) return "Bueno";
    if (score >= 50) return "Regular";
    return "Bajo";
}
function scoreTextCls(score: number): string {
    if (score >= 80) return "text-emerald-700 dark:text-emerald-400";
    if (score >= 65) return "text-blue-700 dark:text-blue-400";
    if (score >= 50) return "text-amber-700 dark:text-amber-400";
    return "text-rose-700 dark:text-rose-400";
}
function scoreBarCls(score: number): string {
    if (score >= 80) return "bg-emerald-500";
    if (score >= 65) return "bg-blue-500";
    if (score >= 50) return "bg-amber-500";
    return "bg-rose-500";
}
function scoreBgCls(score: number): string {
    if (score >= 80) return "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800";
    if (score >= 65) return "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800";
    if (score >= 50) return "bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800";
    return "bg-rose-50 dark:bg-rose-900/20 border-rose-200 dark:border-rose-800";
}

// ── Inline status change dropdown ─────────────────────────────────────────────

interface StatusDropdownProps {
    candidateId: string;
    currentStatus: string;
    onChanged: (id: string, newStatus: string) => void;
}

function StatusDropdown({ candidateId, currentStatus, onChanged }: StatusDropdownProps) {
    const [open, setOpen] = useState(false);
    const [saving, setSaving] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const h = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, [open]);

    const change = async (newStatus: string) => {
        if (newStatus === currentStatus) { setOpen(false); return; }
        setSaving(true);
        setOpen(false);
        try {
            await candidatesApi.updateStatus(candidateId, newStatus);
            onChanged(candidateId, newStatus);
        } catch { /* keep current */ } finally { setSaving(false); }
    };

    const cfg = STATUS_CFG[currentStatus];

    return (
        <div ref={ref} className="relative inline-block">
            <button
                onClick={() => setOpen(o => !o)}
                disabled={saving}
                className={`inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full text-xs font-medium border transition-all ${cfg?.pill ?? "bg-slate-100 text-slate-600 border-slate-200"} hover:opacity-80`}
                title="Cambiar etapa"
            >
                {saving
                    ? <span className="material-symbols-outlined text-[13px] animate-spin">sync</span>
                    : <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg?.dot ?? "bg-slate-400"}`} />
                }
                {cfg?.label ?? currentStatus}
                <span className="material-symbols-outlined text-[14px] opacity-60">expand_more</span>
            </button>

            {open && (
                <div className="absolute top-full left-0 mt-1 z-50 w-40 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden py-1">
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-1.5 pb-1">Mover a</p>
                    {ALL_STATUSES.filter(s => s !== currentStatus).map(s => {
                        const c = STATUS_CFG[s];
                        return (
                            <button
                                key={s}
                                onClick={() => change(s)}
                                className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left"
                            >
                                <span className={`w-2 h-2 rounded-full shrink-0 ${c.dot}`} />
                                {c.label}
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ── Skill autocomplete ────────────────────────────────────────────────────────

interface SkillInputProps { value: string[]; allSkills: string[]; onChange: (s: string[]) => void; }

function SkillInput({ value, allSkills, onChange }: SkillInputProps) {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, []);

    const suggestions = query.length >= 1
        ? allSkills.filter(s => s.toLowerCase().includes(query.toLowerCase()) && !value.includes(s)).slice(0, 8)
        : [];

    return (
        <div ref={ref} className="relative">
            <div className="flex flex-wrap items-center gap-1.5 min-h-[40px] px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary transition-all">
                {value.map(sk => (
                    <span key={sk} className="flex items-center gap-1 bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded-md border border-primary/20">
                        {sk}
                        <button onClick={() => onChange(value.filter(x => x !== sk))} className="hover:opacity-60 transition-opacity">
                            <span className="material-symbols-outlined text-[11px]">close</span>
                        </button>
                    </span>
                ))}
                <input
                    type="text"
                    placeholder={value.length === 0 ? "Ej: Python, Excel, Scrum..." : "Añadir otra..."}
                    value={query}
                    onChange={e => { setQuery(e.target.value); setOpen(true); }}
                    onFocus={() => setOpen(true)}
                    className="flex-1 min-w-[140px] bg-transparent text-sm text-slate-900 dark:text-white placeholder-slate-400 outline-none"
                />
            </div>
            {open && suggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden py-1">
                    {suggestions.map(s => (
                        <button key={s} onMouseDown={e => { e.preventDefault(); onChange([...value, s]); setQuery(""); setOpen(false); }}
                            className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left">
                            <span className="material-symbols-outlined text-[15px] text-slate-400">code</span>
                            {s}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────

const CandidateList: React.FC = () => {
    const [candidates, setCandidates] = useState<CandidateRow[]>([]);
    const [jobs, setJobs] = useState<JobProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadingScores, setLoadingScores] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [total, setTotal] = useState(0);

    // Filters
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedJobId, setSelectedJobId] = useState("all");
    const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
    const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
    const [minScore, setMinScore] = useState(0);
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Bulk selection
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [bulkWorking, setBulkWorking] = useState(false);

    // ── Load ─────────────────────────────────────────────────────────────────

    useEffect(() => {
        (async () => {
            try {
                const [cRes, jRes] = await Promise.all([candidatesApi.list(1, 200), jobsApi.list()]);
                const jobMap: Record<string, string> = {};
                jRes.data.items.forEach(j => { jobMap[j.id] = j.title; });
                setCandidates(cRes.data.items.map(c => ({ ...c, job_title: c.job_id ? jobMap[c.job_id] : undefined })));
                setTotal(cRes.data.total);
                setJobs(jRes.data.items);
            } catch {
                setError("No se pudo cargar la lista. Verifica que el backend esté activo.");
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    // Load match scores when a specific job is selected
    useEffect(() => {
        if (selectedJobId === "all") {
            setCandidates(prev => prev.map(c => ({ ...c, match_score: undefined, recommendation: undefined })));
            setMinScore(0);
            return;
        }
        setLoadingScores(true);
        jobsApi.getScores(selectedJobId)
            .then(res => {
                const map: Record<string, { s: number; r: string; ms: string[]; bs: string[] }> = {};
                res.data.scores.forEach(x => {
                    map[x.candidate_id] = {
                        s: x.overall_score,
                        r: x.recommendation,
                        ms: x.missing_skills ?? [],
                        bs: x.bonus_skills ?? [],
                    };
                });
                setCandidates(prev => prev.map(c => {
                    const x = map[c.id];
                    return x
                        ? { ...c, match_score: x.s, recommendation: x.r, missing_skills: x.ms, bonus_skills: x.bs }
                        : { ...c, match_score: undefined, recommendation: undefined, missing_skills: undefined, bonus_skills: undefined };
                }));
            })
            .catch(() => { })
            .finally(() => setLoadingScores(false));
    }, [selectedJobId]);

    // Inline status change — optimistic update
    const handleStatusChange = useCallback((id: string, newStatus: string) => {
        setCandidates(prev => prev.map(c => c.id === id ? { ...c, status: newStatus } : c));
    }, []);

    // ── Filter & sort ─────────────────────────────────────────────────────────

    const allSkills = useMemo(() => {
        const s = new Set<string>();
        candidates.forEach(c => c.skills.forEach(sk => s.add(sk)));
        return Array.from(s).sort();
    }, [candidates]);

    const filtered = useMemo(() => {
        let r = candidates;
        if (selectedJobId !== "all") r = r.filter(c => c.job_id === selectedJobId);
        if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            r = r.filter(c =>
                c.full_name.toLowerCase().includes(q) ||
                (c.email || "").toLowerCase().includes(q) ||
                c.skills.some(s => s.toLowerCase().includes(q))
            );
        }
        if (selectedStatuses.length > 0) r = r.filter(c => selectedStatuses.includes(c.status));
        if (selectedSkills.length > 0) {
            r = r.filter(c => selectedSkills.every(sk => c.skills.some(cs => cs.toLowerCase().includes(sk.toLowerCase()))));
        }
        if (selectedJobId !== "all" && minScore > 0) r = r.filter(c => (c.match_score ?? 0) >= minScore);
        if (selectedJobId !== "all") r = [...r].sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0));
        return r;
    }, [candidates, searchQuery, selectedJobId, selectedStatuses, selectedSkills, minScore]);

    const toggleStatus = (s: string) =>
        setSelectedStatuses(p => p.includes(s) ? p.filter(x => x !== s) : [...p, s]);

    const activeFilters = (selectedJobId !== "all" ? 1 : 0) + selectedStatuses.length + selectedSkills.length + (minScore > 0 ? 1 : 0);
    const hasSearch = searchQuery.trim().length > 0;
    const showScore = selectedJobId !== "all";

    const clearAll = () => {
        setSearchQuery(""); setSelectedJobId("all"); setSelectedStatuses([]);
        setSelectedSkills([]); setMinScore(0); setSelectedIds(new Set());
    };

    // ── Bulk selection helpers ────────────────────────────────────────────────

    const allFilteredSelected = filtered.length > 0 && filtered.every(c => selectedIds.has(c.id));
    const someFilteredSelected = filtered.some(c => selectedIds.has(c.id));

    const toggleSelectOne = useCallback((id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    }, []);

    const toggleSelectAll = useCallback(() => {
        setSelectedIds(prev => {
            if (filtered.every(c => prev.has(c.id))) {
                // deselect all filtered
                const next = new Set(prev);
                filtered.forEach(c => next.delete(c.id));
                return next;
            }
            // select all filtered
            const next = new Set(prev);
            filtered.forEach(c => next.add(c.id));
            return next;
        });
    }, [filtered]);

    const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

    // Bulk status change — runs all in parallel, optimistic update
    const handleBulkStatus = useCallback(async (newStatus: string) => {
        const ids = Array.from(selectedIds);
        if (ids.length === 0) return;
        setBulkWorking(true);
        // Optimistic
        setCandidates(prev => prev.map(c => ids.includes(c.id) ? { ...c, status: newStatus } : c));
        try {
            await Promise.all(ids.map(id => candidatesApi.updateStatus(id, newStatus)));
            setSelectedIds(new Set());
        } catch {
            // Rollback not feasible without snapshot — reload instead
            const [cRes, jRes] = await Promise.all([candidatesApi.list(1, 200), jobsApi.list()]).catch(() => [null, null]) as [any, any];
            if (cRes) {
                const jobMap: Record<string, string> = {};
                jRes?.data?.items?.forEach((j: any) => { jobMap[j.id] = j.title; });
                setCandidates(cRes.data.items.map((c: any) => ({ ...c, job_title: c.job_id ? jobMap[c.job_id] : undefined })));
            }
        } finally {
            setBulkWorking(false);
        }
    }, [selectedIds]);

    // Bulk export — only selected candidates
    const handleBulkExport = useCallback(() => {
        const ids = Array.from(selectedIds);
        const toExport = filtered.filter(c => ids.includes(c.id));
        const job = jobs.find(j => j.id === selectedJobId);
        const baseName = job
            ? `RecruitAI_${job.title.replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, "").trim().replace(/\s+/g, "_")}_Seleccion`
            : "RecruitAI_Seleccion";
        exportCandidatesCsv(toExport, { baseFilename: baseName, includeScoreColumns: showScore });
    }, [selectedIds, filtered, jobs, selectedJobId, showScore]);

    // Export
    const [exportDone, setExportDone] = useState(false);
    const handleExport = useCallback(() => {
        const job = jobs.find(j => j.id === selectedJobId);
        const baseName = job
            ? `RecruitAI_${job.title.replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, "").trim().replace(/\s+/g, "_")}`
            : "RecruitAI_Candidatos";
        exportCandidatesCsv(filtered, { baseFilename: baseName, includeScoreColumns: showScore });
        setExportDone(true);
        setTimeout(() => setExportDone(false), 2500);
    }, [filtered, jobs, selectedJobId, showScore]);


    // ── Loading state ─────────────────────────────────────────────────────────

    if (loading) return (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
            <span className="material-symbols-outlined text-[48px] text-primary animate-spin">sync</span>
            <p className="text-slate-500 dark:text-slate-400 text-sm">Cargando candidatos...</p>
        </div>
    );

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-5">

            {/* ── Page header ───────────────────────────────────────────────── */}
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Candidatos</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                        {total} en base de datos
                        {filtered.length !== total && (
                            <> · <span className="font-semibold text-primary">{filtered.length} mostrados</span></>
                        )}
                    </p>
                </div>
                <div className="flex items-center gap-2.5">
                    {/* Export button */}
                    <button
                        onClick={handleExport}
                        disabled={filtered.length === 0}
                        className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg border transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed ${exportDone
                            ? "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-300 dark:border-emerald-700 text-emerald-700 dark:text-emerald-400"
                            : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                        }`}
                        title={showScore ? "Exporta candidatos con score IA, recomendación y habilidades faltantes" : "Exporta la lista actual con todos los filtros aplicados"}
                    >
                        <span className="material-symbols-outlined text-[18px]">
                            {exportDone ? "check_circle" : "download"}
                        </span>
                        {exportDone
                            ? "¡Descargado!"
                            : <>Exportar <span className="font-bold text-primary">{filtered.length}</span></>
                        }
                        {showScore && !exportDone && (
                            <span className="ml-0.5 flex items-center gap-0.5 text-[11px] text-primary/70">
                                <span className="material-symbols-outlined text-[12px]">auto_awesome</span>
                                con scores
                            </span>
                        )}
                    </button>

                    <Link href="/data"
                        className="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors shadow-sm">
                        <span className="material-symbols-outlined text-[18px]">upload_file</span>
                        Importar CVs
                    </Link>
                </div>
            </div>

            {/* ── Filter panel ──────────────────────────────────────────────── */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-sm overflow-hidden">

                {/* Search + job always visible */}
                <div className="p-4 flex flex-col sm:flex-row gap-3">
                    {/* Search */}
                    <div className="relative flex-1">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">search</span>
                        <input type="text" placeholder="Buscar por nombre, email o habilidad..."
                            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-9 py-2.5 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all" />
                        {hasSearch && (
                            <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors">
                                <span className="material-symbols-outlined text-[17px]">close</span>
                            </button>
                        )}
                    </div>

                    {/* Job selector */}
                    <div className="relative sm:w-64">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[18px]">work_outline</span>
                        <select value={selectedJobId} onChange={e => setSelectedJobId(e.target.value)}
                            className={`w-full pl-9 pr-8 py-2.5 border rounded-xl text-sm appearance-none focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all ${selectedJobId !== "all"
                                ? "bg-primary/5 border-primary/30 text-primary font-medium"
                                : "bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300"}`}>
                            <option value="all">Todos los puestos</option>
                            {jobs.filter(j => j.status === "active").map(j => (
                                <option key={j.id} value={j.id}>{j.title}{j.candidate_count ? ` (${j.candidate_count})` : ""}</option>
                            ))}
                            {jobs.some(j => j.status !== "active") && (
                                <>
                                    <option disabled>── Inactivos ──</option>
                                    {jobs.filter(j => j.status !== "active").map(j => (
                                        <option key={j.id} value={j.id}>{j.title}</option>
                                    ))}
                                </>
                            )}
                        </select>
                        <span className="absolute right-2.5 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[18px] pointer-events-none">expand_more</span>
                    </div>
                </div>

                {/* Status pills — always visible */}
                <div className="px-4 pb-3">
                    <div className="flex flex-wrap gap-2">
                        {ALL_STATUSES.map(s => {
                            const c = STATUS_CFG[s];
                            const active = selectedStatuses.includes(s);
                            const count = candidates.filter(cd => cd.status === s && (selectedJobId === "all" || cd.job_id === selectedJobId)).length;
                            return (
                                <button key={s} onClick={() => toggleStatus(s)}
                                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${active ? c.activePill : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500"}`}>
                                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${active ? "bg-white/70" : c.dot}`} />
                                    {c.label}
                                    <span className={`text-[10px] font-bold tabular-nums ${active ? "opacity-80" : "text-slate-400"}`}>{count}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Advanced filters toggle */}
                <div className="px-4 pb-3 flex items-center gap-3">
                    <button onClick={() => setShowAdvanced(v => !v)}
                        className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${showAdvanced ? "text-primary" : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"}`}>
                        <span className="material-symbols-outlined text-[16px]">{showAdvanced ? "expand_less" : "expand_more"}</span>
                        Filtros avanzados
                        {(selectedSkills.length > 0 || minScore > 0) && (
                            <span className="bg-primary text-white text-[10px] font-bold w-4 h-4 rounded-full inline-flex items-center justify-center ml-0.5">
                                {selectedSkills.length + (minScore > 0 ? 1 : 0)}
                            </span>
                        )}
                    </button>
                    {(activeFilters > 0 || hasSearch) && (
                        <button onClick={clearAll} className="text-xs text-slate-400 hover:text-rose-500 transition-colors ml-auto flex items-center gap-1">
                            <span className="material-symbols-outlined text-[14px]">clear_all</span>
                            Limpiar todo
                        </button>
                    )}
                </div>

                {/* Advanced section: skills + score */}
                {showAdvanced && (
                    <div className="border-t border-slate-100 dark:border-slate-700 px-4 py-4 grid grid-cols-1 md:grid-cols-2 gap-5 bg-slate-50/50 dark:bg-slate-900/20">
                        {/* Skills */}
                        <div>
                            <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
                                Habilidades requeridas
                            </label>
                            <SkillInput value={selectedSkills} allSkills={allSkills} onChange={setSelectedSkills} />
                            {selectedSkills.length > 0 && (
                                <p className="text-[11px] text-slate-400 mt-1.5">
                                    Solo candidatos con <strong>todas</strong> las habilidades seleccionadas
                                </p>
                            )}
                        </div>

                        {/* Score slider */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <label className={`text-xs font-semibold uppercase tracking-wider ${showScore ? "text-slate-500 dark:text-slate-400" : "text-slate-300 dark:text-slate-600"}`}>
                                    Score mínimo de matching IA
                                </label>
                                {showScore
                                    ? <span className={`text-sm font-bold tabular-nums ${minScore === 0 ? "text-slate-400" : scoreTextCls(minScore)}`}>
                                        {minScore === 0 ? "Sin mínimo" : `≥ ${minScore}%`}
                                    </span>
                                    : <span className="text-[11px] text-slate-400 dark:text-slate-600 italic">Selecciona un puesto primero</span>
                                }
                            </div>
                            <input type="range" min={0} max={90} step={5} value={minScore}
                                disabled={!showScore}
                                onChange={e => setMinScore(Number(e.target.value))}
                                className="w-full accent-primary disabled:opacity-25 disabled:cursor-not-allowed" />
                            <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                                {[0, 30, 60, 90].map(v => <span key={v}>{v}%</span>)}
                            </div>
                        </div>
                    </div>
                )}

                {/* Active filter chips when advanced is closed */}
                {!showAdvanced && (selectedSkills.length > 0 || minScore > 0 || selectedJobId !== "all" || selectedStatuses.length > 0) && (
                    <div className="border-t border-slate-100 dark:border-slate-700 px-4 py-2.5 flex flex-wrap gap-2 bg-slate-50/50 dark:bg-slate-900/20">
                        {selectedJobId !== "all" && (
                            <Chip label={jobs.find(j => j.id === selectedJobId)?.title ?? "Puesto"} icon="work_outline" onRemove={() => setSelectedJobId("all")} />
                        )}
                        {selectedStatuses.map(s => (
                            <Chip key={s} label={STATUS_CFG[s]?.label ?? s} icon="circle" dot={STATUS_CFG[s]?.dot} onRemove={() => toggleStatus(s)} />
                        ))}
                        {selectedSkills.map(sk => (
                            <Chip key={sk} label={sk} icon="code" onRemove={() => setSelectedSkills(selectedSkills.filter(x => x !== sk))} />
                        ))}
                        {minScore > 0 && (
                            <Chip label={`Score ≥ ${minScore}%`} icon="star" onRemove={() => setMinScore(0)} />
                        )}
                    </div>
                )}
            </div>

            {/* ── Status bar ────────────────────────────────────────────────── */}
            <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-500 dark:text-slate-400">
                    <span className="font-semibold text-slate-900 dark:text-white">{filtered.length}</span> candidato{filtered.length !== 1 ? "s" : ""}
                </span>
                {showScore && (
                    <span className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${loadingScores ? "bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800" : "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800"}`}>
                        <span className={`material-symbols-outlined text-[14px] ${loadingScores ? "animate-spin" : ""}`}>
                            {loadingScores ? "sync" : "auto_awesome"}
                        </span>
                        {loadingScores ? "Cargando scores..." : "Ordenado por score IA"}
                    </span>
                )}
            </div>

            {error && (
                <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-amber-700 dark:text-amber-400 flex items-center gap-3 text-sm">
                    <span className="material-symbols-outlined text-[20px]">warning</span>
                    {error}
                </div>
            )}

            {/* ── Table ─────────────────────────────────────────────────────── */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700">
                                {/* Select-all checkbox */}
                                <th className="py-3.5 pl-4 pr-2 w-10">
                                    <input
                                        type="checkbox"
                                        checked={allFilteredSelected}
                                        ref={el => { if (el) el.indeterminate = someFilteredSelected && !allFilteredSelected; }}
                                        onChange={toggleSelectAll}
                                        disabled={filtered.length === 0}
                                        className="w-4 h-4 rounded border-slate-300 dark:border-slate-600 text-primary accent-primary cursor-pointer disabled:opacity-30"
                                        title="Seleccionar todos"
                                    />
                                </th>
                                <th className="py-3.5 px-5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Candidato</th>
                                <th className="py-3.5 px-5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Habilidades</th>
                                <th className="py-3.5 px-5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Experiencia</th>
                                <th className="py-3.5 px-5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Etapa</th>
                                {showScore && (
                                    <th className="py-3.5 px-5 text-left text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                                        <span className="flex items-center gap-1 text-primary">
                                            <span className="material-symbols-outlined text-[14px]">auto_awesome</span>
                                            Match IA
                                        </span>
                                    </th>
                                )}
                                <th className="py-3.5 px-5 text-right text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Perfil</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                            {filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={showScore ? 7 : 6} className="py-20 text-center">
                                        <div className="flex flex-col items-center gap-3">
                                            <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                                                <span className="material-symbols-outlined text-[32px] text-slate-400">
                                                    {activeFilters > 0 || hasSearch ? "search_off" : "person_off"}
                                                </span>
                                            </div>
                                            <p className="font-medium text-slate-600 dark:text-slate-400">
                                                {activeFilters > 0 || hasSearch ? "Sin resultados con estos filtros" : "No hay candidatos aún"}
                                            </p>
                                            <p className="text-sm text-slate-400 max-w-xs">
                                                {activeFilters > 0 || hasSearch
                                                    ? "Prueba ajustando o limpiando los filtros activos."
                                                    : "Importa CVs para comenzar a gestionar tu base de talento."}
                                            </p>
                                            {(activeFilters > 0 || hasSearch)
                                                ? <button onClick={clearAll} className="mt-1 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors">Limpiar filtros</button>
                                                : <Link href="/data" className="mt-1 px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors">Importar CVs</Link>
                                            }
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                filtered.map((c, idx) => {
                                    const bg = avatarBg(c.full_name);
                                    const score = c.match_score;
                                    const isSelected = selectedIds.has(c.id);
                                    return (
                                        <tr key={c.id} className={`group transition-colors ${isSelected ? "bg-primary/5 dark:bg-primary/10" : "hover:bg-slate-50/80 dark:hover:bg-slate-800/40"}`}>

                                            {/* Row checkbox */}
                                            <td className="py-3.5 pl-4 pr-2">
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => toggleSelectOne(c.id)}
                                                    className="w-4 h-4 rounded border-slate-300 dark:border-slate-600 text-primary accent-primary cursor-pointer"
                                                />
                                            </td>

                                            {/* Candidate */}
                                            <td className="py-3.5 px-5">
                                                <div className="flex items-center gap-3">
                                                    {/* Rank number when score active */}
                                                    {showScore && (
                                                        <span className="text-xs font-bold text-slate-300 dark:text-slate-600 w-5 text-center shrink-0">
                                                            {idx + 1}
                                                        </span>
                                                    )}
                                                    <div className={`w-9 h-9 rounded-full ${bg} flex items-center justify-center text-white text-xs font-bold shrink-0 shadow-sm`}>
                                                        {initials(c.full_name)}
                                                    </div>
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{c.full_name}</p>
                                                        {c.email && <p className="text-xs text-slate-400 truncate">{c.email}</p>}
                                                        {c.job_title && (
                                                            <p className="text-[11px] text-slate-400 flex items-center gap-0.5 mt-0.5">
                                                                <span className="material-symbols-outlined text-[11px]">work</span>
                                                                {c.job_title}
                                                            </p>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>

                                            {/* Skills */}
                                            <td className="py-3.5 px-5">
                                                <div className="flex flex-wrap gap-1 max-w-[190px]">
                                                    {c.skills.slice(0, 4).map(sk => {
                                                        const highlighted = selectedSkills.some(s => sk.toLowerCase().includes(s.toLowerCase()));
                                                        return (
                                                            <span key={sk} className={`text-xs px-2 py-0.5 rounded font-medium ${highlighted
                                                                ? "bg-primary/15 text-primary ring-1 ring-primary/30"
                                                                : "bg-slate-100 dark:bg-slate-700/70 text-slate-600 dark:text-slate-300"}`}>
                                                                {sk}
                                                            </span>
                                                        );
                                                    })}
                                                    {c.skills.length > 4 && (
                                                        <span className="text-[11px] text-slate-400 self-center">+{c.skills.length - 4}</span>
                                                    )}
                                                </div>
                                            </td>

                                            {/* Experience */}
                                            <td className="py-3.5 px-5 whitespace-nowrap">
                                                {c.total_experience_years > 0
                                                    ? <span className="text-sm text-slate-700 dark:text-slate-300 font-medium">{c.total_experience_years} <span className="text-slate-400 font-normal">años</span></span>
                                                    : <span className="text-xs text-slate-400 italic">Sin datos</span>}
                                            </td>

                                            {/* Status — inline change */}
                                            <td className="py-3.5 px-5">
                                                <StatusDropdown
                                                    candidateId={c.id}
                                                    currentStatus={c.status}
                                                    onChanged={handleStatusChange}
                                                />
                                            </td>

                                            {/* Score */}
                                            {showScore && (
                                                <td className="py-3.5 px-5">
                                                    {score != null ? (
                                                        <div className={`inline-flex flex-col gap-1 px-3 py-1.5 rounded-xl border ${scoreBgCls(score)}`} style={{ minWidth: 96 }}>
                                                            <div className="flex items-center justify-between gap-2">
                                                                <span className={`text-base font-black tabular-nums leading-none ${scoreTextCls(score)}`}>
                                                                    {Math.round(score)}%
                                                                </span>
                                                                <span className={`text-[10px] font-semibold ${scoreTextCls(score)}`}>
                                                                    {scoreLabel(score)}
                                                                </span>
                                                            </div>
                                                            <div className="h-1.5 bg-black/10 dark:bg-white/10 rounded-full overflow-hidden">
                                                                <div className={`h-full rounded-full ${scoreBarCls(score)} transition-all duration-500`} style={{ width: `${Math.min(score, 100)}%` }} />
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <span className="text-xs text-slate-400 italic px-2">Sin score</span>
                                                    )}
                                                </td>
                                            )}

                                            {/* Profile link */}
                                            <td className="py-3.5 px-5 text-right">
                                                <Link href={`/candidates/${c.id}`}
                                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-primary hover:bg-primary/10 rounded-lg transition-all border border-transparent hover:border-primary/20">
                                                    Ver perfil
                                                    <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                                                </Link>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Footer */}
                {filtered.length > 0 && (
                    <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700 flex items-center justify-between bg-slate-50/50 dark:bg-slate-800/30">
                        <span className="text-xs text-slate-400">
                            {filtered.length} de {total} candidatos
                        </span>
                        {total > 200 && (
                            <span className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
                                <span className="material-symbols-outlined text-[13px]">info</span>
                                Vista limitada a 200 — usa filtros para acotar la búsqueda
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* ── Bulk action floating bar ───────────────────────────────────── */}
            <BulkActionBar
                count={selectedIds.size}
                working={bulkWorking}
                onStatus={handleBulkStatus}
                onExport={handleBulkExport}
                onClear={clearSelection}
            />
        </div>
    );
};

// ── Bulk Action Bar ───────────────────────────────────────────────────────────

interface BulkActionBarProps {
    count: number;
    working: boolean;
    onStatus: (status: string) => void;
    onExport: () => void;
    onClear: () => void;
}

function BulkActionBar({ count, working, onStatus, onExport, onClear }: BulkActionBarProps) {
    const [statusOpen, setStatusOpen] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setStatusOpen(false); };
        document.addEventListener("mousedown", h);
        return () => document.removeEventListener("mousedown", h);
    }, []);

    if (count === 0) return null;

    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50" style={{ animation: "bulkBarIn 0.2s ease-out" }}>
            <div className="flex items-center gap-2 px-4 py-3 bg-slate-900 dark:bg-slate-800 text-white rounded-2xl shadow-2xl border border-slate-700 dark:border-slate-600 min-w-max">

                {/* Count badge */}
                <div className="flex items-center gap-2 pr-3 border-r border-slate-700 dark:border-slate-600">
                    <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center text-[11px] font-black">
                        {count}
                    </div>
                    <span className="text-sm font-medium text-slate-200">
                        {count === 1 ? "candidato seleccionado" : "candidatos seleccionados"}
                    </span>
                </div>

                {/* Mover a dropdown */}
                <div ref={ref} className="relative">
                    <button
                        onClick={() => setStatusOpen(o => !o)}
                        disabled={working}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        <span className="material-symbols-outlined text-[16px]">swap_horiz</span>
                        Mover a
                        <span className="material-symbols-outlined text-[14px] opacity-60">expand_more</span>
                    </button>
                    {statusOpen && (
                        <div className="absolute bottom-full mb-2 left-0 w-44 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden py-1">
                            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-3 pt-1.5 pb-1">Cambiar etapa a</p>
                            {ALL_STATUSES.map(s => {
                                const cfg = STATUS_CFG[s];
                                return (
                                    <button
                                        key={s}
                                        onClick={() => { setStatusOpen(false); onStatus(s); }}
                                        className="w-full flex items-center gap-2.5 px-3 py-1.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors text-left"
                                    >
                                        <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
                                        {cfg.label}
                                    </button>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Quick reject */}
                <button
                    onClick={() => onStatus("rejected")}
                    disabled={working}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-sm font-medium transition-colors disabled:opacity-50"
                >
                    {working
                        ? <span className="material-symbols-outlined text-[16px] animate-spin">sync</span>
                        : <span className="material-symbols-outlined text-[16px]">person_off</span>
                    }
                    Rechazar
                </button>

                {/* Export selection */}
                <button
                    onClick={onExport}
                    disabled={working}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-sm font-medium transition-colors disabled:opacity-50"
                >
                    <span className="material-symbols-outlined text-[16px]">download</span>
                    Exportar
                </button>

                {/* Divider + clear */}
                <div className="w-px h-6 bg-slate-700 dark:bg-slate-600 mx-1" />
                <button
                    onClick={onClear}
                    className="flex items-center gap-1 px-2 py-2 rounded-xl hover:bg-white/10 text-slate-400 hover:text-white text-xs transition-colors"
                    title="Deseleccionar todo"
                >
                    <span className="material-symbols-outlined text-[16px]">close</span>
                </button>
            </div>
        </div>
    );
}

// ── Chip component (active filter pill) ───────────────────────────────────────

function Chip({ label, icon, dot, onRemove }: { label: string; icon: string; dot?: string; onRemove: () => void }) {
    return (
        <span className="inline-flex items-center gap-1.5 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium pl-2.5 pr-2 py-1 rounded-full">
            {dot
                ? <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
                : <span className="material-symbols-outlined text-[13px] text-slate-400">{icon}</span>
            }
            {label}
            <button onClick={onRemove} className="hover:text-rose-500 transition-colors ml-0.5">
                <span className="material-symbols-outlined text-[12px]">close</span>
            </button>
        </span>
    );
}

export default CandidateList;
