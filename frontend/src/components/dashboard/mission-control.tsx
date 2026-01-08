"use client";

import { cn } from "@/lib/utils";

// KPI Card Component
interface KPICardProps {
    title: string;
    value: string;
    icon: string;
    iconColor: string;
    badge?: {
        text: string;
        color: string;
        icon?: string;
    };
    sparkline?: boolean;
    airbyte?: boolean;
}

function KPICard({ title, value, icon, iconColor, badge, sparkline, airbyte }: KPICardProps) {
    const colorMap: Record<string, string> = {
        emerald: "bg-emerald-500/10 text-emerald-500",
        blue: "bg-[#135bec]/10 text-[#135bec]",
        indigo: "bg-indigo-500/10 text-indigo-500",
        amber: "bg-amber-500/10 text-amber-500",
    };

    const badgeColorMap: Record<string, string> = {
        emerald: "text-emerald-500 bg-emerald-500/10",
        blue: "text-[#135bec] bg-[#135bec]/10",
    };

    return (
        <div className="p-5 rounded-xl bg-[#1e293b] border border-[#334155] shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
            {airbyte && (
                <div className="absolute top-0 right-0 p-3">
                    <div className="flex items-center gap-1.5 bg-slate-800/50 backdrop-blur px-2 py-1 rounded border border-slate-700">
                        <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span className="text-[10px] uppercase font-bold text-slate-400">Airbyte Activo</span>
                    </div>
                </div>
            )}

            <div className="flex justify-between items-start mb-4">
                <div className={cn("p-2 rounded-lg", colorMap[iconColor])}>
                    <span className="material-symbols-outlined text-[24px]">{icon}</span>
                </div>

                {badge && (
                    <span className={cn(
                        "flex items-center text-xs font-medium px-2 py-1 rounded-full",
                        badgeColorMap[badge.color]
                    )}>
                        {badge.icon && (
                            <span className="material-symbols-outlined text-[14px] mr-1">{badge.icon}</span>
                        )}
                        {badge.text}
                    </span>
                )}

                {sparkline && (
                    <div className="h-6 w-16">
                        <svg className="w-full h-full stroke-indigo-500 fill-none stroke-2" viewBox="0 0 60 20">
                            <path d="M0 15 L10 12 L20 16 L30 8 L40 10 L50 4 L60 6"></path>
                        </svg>
                    </div>
                )}
            </div>

            <div>
                <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
                <h3 className="text-2xl font-bold text-white">{value}</h3>
            </div>
        </div>
    );
}

// Job Card Component
interface JobCardProps {
    title: string;
    department: string;
    departmentColor: string;
    timeAgo: string;
    candidates: number;
    funnel: {
        applied: number;
        interview: number;
        offer: number;
    };
    recruiters: number;
}

function JobCard({ title, department, departmentColor, timeAgo, candidates, funnel, recruiters }: JobCardProps) {
    const total = funnel.applied + funnel.interview + funnel.offer || 1;

    const deptColorMap: Record<string, string> = {
        purple: "bg-purple-100 text-purple-700 dark:bg-purple-500/10 dark:text-purple-400 border-purple-200 dark:border-purple-500/20",
        orange: "bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400 border-orange-200 dark:border-orange-500/20",
        blue: "bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400 border-blue-200 dark:border-blue-500/20",
        rose: "bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400 border-rose-200 dark:border-rose-500/20",
        teal: "bg-teal-100 text-teal-700 dark:bg-teal-500/10 dark:text-teal-400 border-teal-200 dark:border-teal-500/20",
    };

    return (
        <div className="flex flex-col bg-[#1e293b] border border-[#334155] rounded-xl p-5 shadow-sm hover:shadow-lg transition-all group">
            <div className="flex justify-between items-start mb-4">
                <div>
                    <div className="flex items-center gap-2 mb-2">
                        <span className={cn(
                            "px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider border",
                            deptColorMap[departmentColor]
                        )}>
                            {department}
                        </span>
                        <span className="text-xs text-slate-400 flex items-center gap-1">
                            <span className="material-symbols-outlined text-[14px]">schedule</span>
                            {timeAgo}
                        </span>
                    </div>
                    <h3 className="text-lg font-bold text-white group-hover:text-[#135bec] transition-colors">
                        {title}
                    </h3>
                </div>
                <button className="text-slate-400 hover:text-white transition-colors">
                    <span className="material-symbols-outlined">more_horiz</span>
                </button>
            </div>

            <div className="mb-6">
                <div className="flex justify-between text-xs font-medium text-slate-400 mb-2">
                    <span>Salud del Embudo</span>
                    <span className="text-white">{candidates} Candidatos</span>
                </div>
                <div className="flex h-2.5 w-full rounded-full overflow-hidden bg-slate-800">
                    <div
                        className="h-full bg-emerald-500"
                        style={{ width: `${(funnel.applied / total) * 100}%` }}
                        title={`Aplicado: ${funnel.applied}`}
                    />
                    <div
                        className="h-full bg-amber-500"
                        style={{ width: `${(funnel.interview / total) * 100}%` }}
                        title={`Entrevista: ${funnel.interview}`}
                    />
                    <div
                        className="h-full bg-[#135bec]"
                        style={{ width: `${(funnel.offer / total) * 100}%` }}
                        title={`Oferta: ${funnel.offer}`}
                    />
                </div>
                <div className="flex justify-between mt-1 text-[10px] text-slate-400">
                    <span className="text-emerald-500">Aplicado</span>
                    <span className="text-amber-500">Entrevista</span>
                    <span className="text-[#135bec]">Oferta</span>
                </div>
            </div>

            <div className="mt-auto flex items-center justify-between pt-4 border-t border-slate-800/50">
                <div className="flex -space-x-2 overflow-hidden">
                    {Array.from({ length: Math.min(recruiters, 3) }).map((_, i) => (
                        <div
                            key={i}
                            className="inline-block size-8 rounded-full ring-2 ring-[#1e293b] bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center"
                        >
                            <span className="text-xs text-white font-medium">R{i + 1}</span>
                        </div>
                    ))}
                    {recruiters > 3 && (
                        <div className="flex items-center justify-center size-8 rounded-full ring-2 ring-[#1e293b] bg-slate-700 text-xs font-medium text-slate-300">
                            +{recruiters - 3}
                        </div>
                    )}
                </div>
                <button className="text-sm font-medium text-[#135bec] hover:text-[#135bec]/80 transition-colors flex items-center gap-1">
                    Ver Candidatos
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                </button>
            </div>
        </div>
    );
}

// Main Mission Control Component
export function MissionControl() {
    const kpis: KPICardProps[] = [
        {
            title: "Tiempo Promedio de Contratación",
            value: "14 Días",
            icon: "timer",
            iconColor: "emerald",
            badge: { text: "2 días", icon: "trending_down", color: "emerald" },
        },
        {
            title: "Candidatos en Proceso",
            value: "1,240",
            icon: "groups",
            iconColor: "blue",
            badge: { text: "+45 nuevos", color: "blue" },
        },
        {
            title: "Tasa de Progreso en el Embudo",
            value: "18%",
            icon: "filter_alt",
            iconColor: "indigo",
            sparkline: true,
        },
        {
            title: "Estado de Ingesta de Datos",
            value: "99.8%",
            icon: "cloud_sync",
            iconColor: "amber",
            airbyte: true,
        },
    ];

    const activeJobs: JobCardProps[] = [
        {
            title: "Ingeniero Backend Senior",
            department: "Ingeniería",
            departmentColor: "purple",
            timeAgo: "hace 2d",
            candidates: 142,
            funnel: { applied: 85, interview: 42, offer: 15 },
            recruiters: 4,
        },
        {
            title: "Diseñador de Producto",
            department: "Producto",
            departmentColor: "orange",
            timeAgo: "hace 5h",
            candidates: 45,
            funnel: { applied: 9, interview: 31, offer: 5 },
            recruiters: 1,
        },
        {
            title: "Ejecutivo de Cuentas",
            department: "Ventas",
            departmentColor: "blue",
            timeAgo: "hace 1s",
            candidates: 88,
            funnel: { applied: 35, interview: 18, offer: 35 },
            recruiters: 3,
        },
        {
            title: "Coordinador de RRHH",
            department: "Operaciones",
            departmentColor: "rose",
            timeAgo: "hace 3d",
            candidates: 204,
            funnel: { applied: 153, interview: 31, offer: 20 },
            recruiters: 1,
        },
        {
            title: "Investigador UX",
            department: "Diseño",
            departmentColor: "teal",
            timeAgo: "hace 12h",
            candidates: 12,
            funnel: { applied: 11, interview: 1, offer: 0 },
            recruiters: 2,
        },
        {
            title: "Arquitecto Frontend",
            department: "Ingeniería",
            departmentColor: "purple",
            timeAgo: "hace 4d",
            candidates: 56,
            funnel: { applied: 28, interview: 14, offer: 14 },
            recruiters: 1,
        },
    ];

    return (
        <>
            {/* KPI Grid */}
            <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {kpis.map((kpi, i) => (
                    <KPICard key={i} {...kpi} />
                ))}
            </section>

            {/* Active Jobs Header */}
            <div className="flex items-center justify-between pt-4">
                <h2 className="text-xl font-bold text-white">Vacantes Activas</h2>
                <div className="flex gap-2">
                    <button className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-300 bg-[#1e293b] border border-[#334155] rounded-lg hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined text-[18px]">filter_list</span>
                        Filtrar
                    </button>
                    <button className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-300 bg-[#1e293b] border border-[#334155] rounded-lg hover:bg-slate-700 transition-colors">
                        <span className="material-symbols-outlined text-[18px]">sort</span>
                        Ordenar
                    </button>
                </div>
            </div>

            {/* Active Jobs Grid */}
            <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 pb-12">
                {activeJobs.map((job, i) => (
                    <JobCard key={i} {...job} />
                ))}
            </section>
        </>
    );
}
