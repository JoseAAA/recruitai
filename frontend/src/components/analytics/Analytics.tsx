"use client";

import { useState, useEffect } from "react";
import { statsApi, DashboardStats } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────
const STATUS_LABELS: Record<string, string> = {
    new: "Nuevos",
    screening: "Screening",
    interview: "Entrevista",
    offer: "Oferta",
    hired: "Contratados",
    rejected: "Descartados",
};

const STATUS_COLORS: Record<string, string> = {
    new: "bg-slate-400",
    screening: "bg-indigo-400",
    interview: "bg-amber-400",
    offer: "bg-emerald-400",
    hired: "bg-primary",
    rejected: "bg-red-400",
};

const STATUS_ICON: Record<string, string> = {
    new: "fiber_new",
    screening: "search",
    interview: "groups",
    offer: "handshake",
    hired: "check_circle",
    rejected: "cancel",
};

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "—";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `hace ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `hace ${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `hace ${days}d`;
}

// ── Component ────────────────────────────────────────────
const Analytics: React.FC = () => {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        statsApi
            .dashboard()
            .then((res) => setStats(res.data))
            .catch(() => setError("No se pudo conectar con el servidor"))
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-24 space-y-3">
                <span className="material-symbols-outlined text-[48px] text-primary animate-spin">
                    sync
                </span>
                <p className="text-slate-400">Cargando analítica…</p>
            </div>
        );
    }

    if (error || !stats) {
        return (
            <div className="flex flex-col items-center justify-center py-24 space-y-3">
                <span className="material-symbols-outlined text-[48px] text-red-400">
                    cloud_off
                </span>
                <p className="text-slate-400">{error ?? "Sin datos disponibles"}</p>
            </div>
        );
    }

    // Compute pipeline stages in order (only statuses that exist)
    const pipelineOrder = ["new", "screening", "interview", "offer", "hired"];
    const pipeline = pipelineOrder
        .map((key) => ({
            key,
            label: STATUS_LABELS[key] ?? key,
            count: stats.candidates_by_status[key] ?? 0,
            color: STATUS_COLORS[key] ?? "bg-slate-400",
            icon: STATUS_ICON[key] ?? "circle",
        }))
        .filter((s) => s.count > 0 || s.key === "new"); // Always show "Nuevos"

    const maxPipeline = Math.max(...pipeline.map((s) => s.count), 1);
    const rejectedCount = stats.candidates_by_status["rejected"] ?? 0;

    return (
        <>
            {/* ── Header ── */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                    Resumen de Reclutamiento
                </h1>
                <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                    Estado actual de las convocatorias y candidatos.
                </p>
            </div>

            {/* ── Section 1: KPI Cards — "¿Cómo vamos?" ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                {/* Card: Total Candidatos */}
                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex justify-between items-start mb-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <span className="material-symbols-outlined text-blue-500 text-[24px]">
                                group
                            </span>
                        </div>
                    </div>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-1">
                        Candidatos Totales
                    </p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">
                        {stats.total_candidates}
                    </p>
                </div>

                {/* Card: Vacantes Activas */}
                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex justify-between items-start mb-3">
                        <div className="p-2 rounded-lg bg-emerald-500/10">
                            <span className="material-symbols-outlined text-emerald-500 text-[24px]">
                                work
                            </span>
                        </div>
                    </div>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-1">
                        Vacantes Activas
                    </p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">
                        {stats.active_jobs}
                        <span className="text-base font-normal text-slate-400 ml-1">
                            / {stats.total_jobs}
                        </span>
                    </p>
                </div>

                {/* Card: Nuevos esta semana */}
                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex justify-between items-start mb-3">
                        <div className="p-2 rounded-lg bg-amber-500/10">
                            <span className="material-symbols-outlined text-amber-500 text-[24px]">
                                person_add
                            </span>
                        </div>
                        {stats.new_candidates_this_week > 0 && (
                            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">
                                +{stats.new_candidates_this_week}
                            </span>
                        )}
                    </div>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-1">
                        Nuevos esta Semana
                    </p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">
                        {stats.new_candidates_this_week}
                    </p>
                </div>

                {/* Card: Descartados */}
                <div className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex justify-between items-start mb-3">
                        <div className="p-2 rounded-lg bg-red-500/10">
                            <span className="material-symbols-outlined text-red-500 text-[24px]">
                                person_off
                            </span>
                        </div>
                    </div>
                    <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-1">
                        Descartados
                    </p>
                    <p className="text-3xl font-bold text-slate-900 dark:text-white">
                        {rejectedCount}
                    </p>
                </div>
            </div>

            {/* ── Section 2: Pipeline de Contratación — "¿Dónde están?" ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* Pipeline Funnel */}
                <div className="lg:col-span-2 bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">
                        Pipeline de Contratación
                    </h3>
                    <p className="text-xs text-slate-400 mb-5">
                        ¿En qué etapa están los candidatos?
                    </p>
                    <div className="space-y-3">
                        {pipeline.map((stage) => (
                            <div key={stage.key} className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-[20px] text-slate-400 w-6">
                                    {stage.icon}
                                </span>
                                <span className="text-sm font-medium text-slate-600 dark:text-slate-300 w-24 flex-shrink-0">
                                    {stage.label}
                                </span>
                                <div className="flex-1 h-6 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden relative">
                                    <div
                                        className={`h-full ${stage.color} rounded-full transition-all duration-700 flex items-center justify-end pr-2`}
                                        style={{
                                            width: `${Math.max((stage.count / maxPipeline) * 100, 8)}%`,
                                        }}
                                    >
                                        <span className="text-xs font-bold text-white drop-shadow">
                                            {stage.count}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Pipeline Summary */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm flex flex-col justify-between">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">
                            Distribución
                        </h3>
                        <p className="text-xs text-slate-400 mb-5">
                            Porcentaje por etapa
                        </p>
                    </div>
                    <div className="space-y-3">
                        {pipeline.map((stage) => {
                            const pct =
                                stats.total_candidates > 0
                                    ? Math.round(
                                          (stage.count / stats.total_candidates) * 100
                                      )
                                    : 0;
                            return (
                                <div
                                    key={stage.key}
                                    className="flex items-center justify-between"
                                >
                                    <div className="flex items-center gap-2">
                                        <div
                                            className={`w-2.5 h-2.5 rounded-full ${stage.color}`}
                                        ></div>
                                        <span className="text-sm text-slate-600 dark:text-slate-300">
                                            {stage.label}
                                        </span>
                                    </div>
                                    <span className="text-sm font-bold text-slate-700 dark:text-slate-200">
                                        {pct}%
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* ── Section 3: Actividad Reciente — "¿Qué novedades hay?" ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Recent Candidates */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">
                        Últimos Candidatos
                    </h3>
                    <p className="text-xs text-slate-400 mb-4">
                        Los 5 perfiles más recientes
                    </p>
                    {stats.recent_candidates.length > 0 ? (
                        <div className="space-y-2">
                            {stats.recent_candidates.map((c) => (
                                <div
                                    key={c.id}
                                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                >
                                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center flex-shrink-0">
                                        <span className="text-white text-xs font-bold">
                                            {c.full_name
                                                .split(" ")
                                                .map((n) => n[0])
                                                .join("")
                                                .slice(0, 2)
                                                .toUpperCase()}
                                        </span>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                                            {c.full_name}
                                        </p>
                                        <p className="text-xs text-slate-400">
                                            {c.skills_count} habilidades · {timeAgo(c.created_at)}
                                        </p>
                                    </div>
                                    <span
                                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                            c.status === "new"
                                                ? "bg-slate-100 dark:bg-slate-700 text-slate-500"
                                                : c.status === "hired"
                                                ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600"
                                                : "bg-blue-50 dark:bg-blue-900/20 text-blue-500"
                                        }`}
                                    >
                                        {STATUS_LABELS[c.status] ?? c.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400 text-center py-8">
                            Aún no hay candidatos cargados
                        </p>
                    )}
                </div>

                {/* Recent Jobs */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-1">
                        Últimas Convocatorias
                    </h3>
                    <p className="text-xs text-slate-400 mb-4">
                        Los 5 puestos más recientes
                    </p>
                    {stats.recent_jobs.length > 0 ? (
                        <div className="space-y-2">
                            {stats.recent_jobs.map((j) => (
                                <div
                                    key={j.id}
                                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
                                >
                                    <div className="p-2 rounded-lg bg-primary/10 flex-shrink-0">
                                        <span className="material-symbols-outlined text-primary text-[20px]">
                                            work
                                        </span>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                                            {j.title}
                                        </p>
                                        <p className="text-xs text-slate-400">
                                            {j.required_skills_count} requisitos ·{" "}
                                            {timeAgo(j.created_at)}
                                        </p>
                                    </div>
                                    <span
                                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                            j.status === "active"
                                                ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600"
                                                : "bg-slate-100 dark:bg-slate-700 text-slate-500"
                                        }`}
                                    >
                                        {j.status === "active" ? "Activo" : j.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400 text-center py-8">
                            Aún no hay convocatorias creadas
                        </p>
                    )}
                </div>
            </div>
        </>
    );
};

export default Analytics;
