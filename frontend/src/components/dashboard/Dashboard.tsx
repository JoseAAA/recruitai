"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { statsApi, DashboardStats, api } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────
const STATUS_LABELS: Record<string, string> = {
    new: "Nuevos",
    screening: "En Revisión",
    interview: "Entrevista",
    offer: "Oferta",
    hired: "Contratados",
    rejected: "Descartados",
};

const STATUS_DOT: Record<string, string> = {
    new: "bg-slate-400",
    screening: "bg-indigo-400",
    interview: "bg-amber-400",
    offer: "bg-emerald-400",
    hired: "bg-primary",
    rejected: "bg-red-400",
};

function timeAgo(dateStr: string | null): string {
    if (!dateStr) return "";
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "ahora";
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `${days}d`;
}

// ── Component ────────────────────────────────────────────
const Dashboard = () => {
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
                <p className="text-slate-400">Cargando panel…</p>
            </div>
        );
    }

    if (error || !stats) {
        return (
            <div className="flex flex-col items-center justify-center py-24 space-y-3">
                <span className="material-symbols-outlined text-[48px] text-red-400">
                    cloud_off
                </span>
                <p className="text-slate-400">{error ?? "Sin datos"}</p>
            </div>
        );
    }

    const pendingReview =
        (stats.candidates_by_status["new"] ?? 0) +
        (stats.candidates_by_status["screening"] ?? 0);
    const inInterview = stats.candidates_by_status["interview"] ?? 0;
    const hired = stats.candidates_by_status["hired"] ?? 0;

    return (
        <>
            {/* ── Greeting ── */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                    Panel de Control
                </h1>
                <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                    Resumen del día — {new Date().toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" })}
                </p>
            </div>

            {/* ── KPI Strip ── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <KpiCard
                    icon="group"
                    iconBg="bg-blue-500/10"
                    iconColor="text-blue-500"
                    label="Candidatos"
                    value={stats.total_candidates}
                />
                <KpiCard
                    icon="work"
                    iconBg="bg-emerald-500/10"
                    iconColor="text-emerald-500"
                    label="Vacantes Activas"
                    value={stats.active_jobs}
                />
                <KpiCard
                    icon="rate_review"
                    iconBg="bg-amber-500/10"
                    iconColor="text-amber-500"
                    label="Pendientes de Revisión"
                    value={pendingReview}
                    alert={pendingReview > 0}
                />
                <KpiCard
                    icon="check_circle"
                    iconBg="bg-primary/10"
                    iconColor="text-primary"
                    label="Contratados"
                    value={hired}
                />
            </div>

            {/* ── Main Content: Two Columns ── */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">

                {/* LEFT: Activiy Feed (3 cols) */}
                <div className="lg:col-span-3 bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 dark:text-white">
                                Actividad Reciente
                            </h2>
                            <p className="text-xs text-slate-400">Últimos candidatos procesados</p>
                        </div>
                        <Link
                            href="/candidates"
                            className="text-xs text-primary hover:underline font-medium flex items-center gap-1"
                        >
                            Ver todos
                            <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
                        </Link>
                    </div>

                    {stats.recent_candidates.length > 0 ? (
                        <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                            {stats.recent_candidates.map((c) => (
                                <Link
                                    key={c.id}
                                    href={`/candidates/${c.id}`}
                                    className="flex items-center gap-3 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/30 -mx-2 px-2 rounded-lg transition-colors"
                                >
                                    {/* Avatar */}
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

                                    {/* Info */}
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                                            {c.full_name}
                                        </p>
                                        <p className="text-xs text-slate-400">
                                            {c.skills_count} habilidades
                                        </p>
                                    </div>

                                    {/* Status + Time */}
                                    <div className="flex items-center gap-2 flex-shrink-0">
                                        <span className="flex items-center gap-1.5 text-xs text-slate-500">
                                            <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[c.status] ?? "bg-slate-400"}`}></span>
                                            {STATUS_LABELS[c.status] ?? c.status}
                                        </span>
                                        <span className="text-xs text-slate-400">
                                            {timeAgo(c.created_at)}
                                        </span>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    ) : (
                        <EmptyState
                            icon="person_search"
                            title="Sin candidatos aún"
                            subtitle="Importa CVs para comenzar"
                        />
                    )}
                </div>

                {/* RIGHT: Quick Status + Actions (2 cols) */}
                <div className="lg:col-span-2 space-y-4">
                    {/* Pipeline Summary */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h2 className="text-base font-bold text-slate-900 dark:text-white mb-3">
                            Estado del Pipeline
                        </h2>
                        <div className="space-y-2.5">
                            {["new", "screening", "interview", "offer", "hired"].map((key) => {
                                const count = stats.candidates_by_status[key] ?? 0;
                                const pct =
                                    stats.total_candidates > 0
                                        ? Math.round((count / stats.total_candidates) * 100)
                                        : 0;
                                return (
                                    <div key={key} className="flex items-center gap-3">
                                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[key]}`}></span>
                                        <span className="text-sm text-slate-600 dark:text-slate-300 flex-1">
                                            {STATUS_LABELS[key]}
                                        </span>
                                        <span className="text-sm font-bold text-slate-700 dark:text-slate-200 w-8 text-right">
                                            {count}
                                        </span>
                                        <span className="text-xs text-slate-400 w-10 text-right">
                                            {pct}%
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Recent Jobs */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="text-base font-bold text-slate-900 dark:text-white">
                                Convocatorias
                            </h2>
                            <Link
                                href="/jobs"
                                className="text-xs text-primary hover:underline font-medium"
                            >
                                Ver todas
                            </Link>
                        </div>
                        {stats.recent_jobs.length > 0 ? (
                            <div className="space-y-2">
                                {stats.recent_jobs.slice(0, 3).map((j) => (
                                    <Link
                                        key={j.id}
                                        href="/jobs"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                                    >
                                        <div className="p-1.5 rounded-lg bg-primary/10 flex-shrink-0">
                                            <span className="material-symbols-outlined text-primary text-[18px]">
                                                work
                                            </span>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                                                {j.title}
                                            </p>
                                            <p className="text-xs text-slate-400">
                                                {j.required_skills_count} requisitos
                                            </p>
                                        </div>
                                        <span
                                            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                                j.status === "active" ? "bg-emerald-400" : "bg-slate-400"
                                            }`}
                                        ></span>
                                    </Link>
                                ))}
                            </div>
                        ) : (
                            <EmptyState
                                icon="work_off"
                                title="Sin convocatorias"
                                subtitle="Crea tu primer perfil"
                            />
                        )}
                    </div>
                </div>
            </div>

            {/* ── Quick Actions — minimal row ── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <QuickAction
                    href="/jobs"
                    icon="add_circle"
                    iconColor="text-primary"
                    iconBg="bg-primary/10"
                    label="Nueva Convocatoria"
                />
                <QuickAction
                    href="/data"
                    icon="upload_file"
                    iconColor="text-emerald-500"
                    iconBg="bg-emerald-500/10"
                    label="Importar CVs"
                />
                <QuickAction
                    href="/analytics"
                    icon="insights"
                    iconColor="text-amber-500"
                    iconBg="bg-amber-500/10"
                    label="Ver Analítica"
                />
            </div>
        </>
    );
};

// ── Sub-components ───────────────────────────────────────

function KpiCard({
    icon,
    iconBg,
    iconColor,
    label,
    value,
    alert = false,
}: {
    icon: string;
    iconBg: string;
    iconColor: string;
    label: string;
    value: number;
    alert?: boolean;
}) {
    return (
        <div
            className={`p-4 rounded-xl bg-white dark:bg-slate-800/50 border shadow-sm ${
                alert
                    ? "border-amber-400/50 dark:border-amber-500/30"
                    : "border-slate-200 dark:border-slate-700"
            }`}
        >
            <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${iconBg} flex-shrink-0`}>
                    <span className={`material-symbols-outlined ${iconColor} text-[22px]`}>
                        {icon}
                    </span>
                </div>
                <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                        {label}
                    </p>
                    <p className="text-xl font-bold text-slate-900 dark:text-white">
                        {value}
                    </p>
                </div>
            </div>
        </div>
    );
}

function QuickAction({
    href,
    icon,
    iconColor,
    iconBg,
    label,
}: {
    href: string;
    icon: string;
    iconColor: string;
    iconBg: string;
    label: string;
}) {
    return (
        <Link
            href={href}
            className="flex items-center gap-3 p-3.5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 transition-all group"
        >
            <div className={`p-2 rounded-lg ${iconBg} group-hover:scale-110 transition-transform flex-shrink-0`}>
                <span className={`material-symbols-outlined ${iconColor} text-[20px]`}>
                    {icon}
                </span>
            </div>
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {label}
            </span>
        </Link>
    );
}

function EmptyState({ icon, title, subtitle }: { icon: string; title: string; subtitle: string }) {
    return (
        <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="material-symbols-outlined text-[36px] text-slate-300 mb-2">
                {icon}
            </span>
            <p className="text-sm text-slate-500 font-medium">{title}</p>
            <p className="text-xs text-slate-400">{subtitle}</p>
        </div>
    );
}

export default Dashboard;
