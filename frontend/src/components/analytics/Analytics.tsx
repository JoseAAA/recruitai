"use client";

const Analytics: React.FC = () => {
    const metrics = [
        { label: "Candidatos Totales", value: "3,847", change: "+12%", icon: "group" },
        { label: "Vacantes Activas", value: "24", change: "+3", icon: "work" },
        { label: "Tiempo Promedio", value: "18 días", change: "-4 días", icon: "timer" },
        { label: "Tasa de Conversión", value: "23%", change: "+5%", icon: "trending_up" },
    ];

    const funnelData = [
        { stage: "Aplicaciones", count: 1200, color: "bg-slate-300" },
        { stage: "Screening", count: 450, color: "bg-indigo-400" },
        { stage: "Entrevista", count: 180, color: "bg-amber-400" },
        { stage: "Oferta", count: 45, color: "bg-emerald-400" },
        { stage: "Contratados", count: 28, color: "bg-primary" },
    ];

    const topSources = [
        { name: "LinkedIn", candidates: 1250, percentage: 42 },
        { name: "Indeed", candidates: 890, percentage: 30 },
        { name: "Referidos", candidates: 420, percentage: 14 },
        { name: "Portal Web", candidates: 287, percentage: 10 },
        { name: "Otros", candidates: 120, percentage: 4 },
    ];

    return (
        <>
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Analítica de Reclutamiento
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Métricas y estadísticas del proceso de contratación.
                    </p>
                </div>
                <div className="flex gap-2">
                    <select className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none">
                        <option>Últimos 30 días</option>
                        <option>Últimos 90 días</option>
                        <option>Este año</option>
                    </select>
                    <button className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px]">download</span>
                        Exportar
                    </button>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {metrics.map((m, i) => (
                    <div
                        key={i}
                        className="p-5 rounded-xl bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 shadow-sm"
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="p-2 rounded-lg bg-primary/10">
                                <span className="material-symbols-outlined text-primary text-[24px]">
                                    {m.icon}
                                </span>
                            </div>
                            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">
                                {m.change}
                            </span>
                        </div>
                        <p className="text-slate-500 dark:text-slate-400 text-sm font-medium mb-1">
                            {m.label}
                        </p>
                        <p className="text-2xl font-bold text-slate-900 dark:text-white">
                            {m.value}
                        </p>
                    </div>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Funnel */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-6">
                        Embudo de Contratación
                    </h3>
                    <div className="space-y-4">
                        {funnelData.map((stage, i) => (
                            <div key={i}>
                                <div className="flex justify-between text-sm mb-1">
                                    <span className="font-medium text-slate-700 dark:text-slate-300">
                                        {stage.stage}
                                    </span>
                                    <span className="text-slate-500">{stage.count}</span>
                                </div>
                                <div className="h-3 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full ${stage.color} transition-all duration-500`}
                                        style={{ width: `${(stage.count / 1200) * 100}%` }}
                                    ></div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Top Sources */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-6">
                        Fuentes de Candidatos
                    </h3>
                    <div className="space-y-4">
                        {topSources.map((source, i) => (
                            <div key={i} className="flex items-center gap-4">
                                <div className="flex-1">
                                    <div className="flex justify-between text-sm mb-1">
                                        <span className="font-medium text-slate-700 dark:text-slate-300">
                                            {source.name}
                                        </span>
                                        <span className="text-slate-500">
                                            {source.candidates} ({source.percentage}%)
                                        </span>
                                    </div>
                                    <div className="h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-primary transition-all duration-500"
                                            style={{ width: `${source.percentage}%` }}
                                        ></div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Time to Hire Chart Placeholder */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-6">
                    Tiempo de Contratación por Departamento
                </h3>
                <div className="h-64 flex items-center justify-center bg-slate-50 dark:bg-slate-800/50 rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-700">
                    <div className="text-center text-slate-400">
                        <span className="material-symbols-outlined text-[48px] mb-2">insights</span>
                        <p className="text-sm">Gráfico de tiempo de contratación</p>
                        <p className="text-xs">Próximamente con datos reales</p>
                    </div>
                </div>
            </div>
        </>
    );
};

export default Analytics;
