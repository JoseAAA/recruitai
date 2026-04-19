"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const Sidebar: React.FC = () => {
    const pathname = usePathname();
    const { user, logout, sessionWarning, dismissSessionWarning } = useAuth();

    const navItems = [
        { path: "/", label: "Panel de Control", icon: "dashboard" },
        { path: "/jobs", label: "Perfiles de Puesto", icon: "work" },
        { path: "/analytics", label: "Analítica", icon: "bar_chart" },
    ];

    const systemItems = [
        { path: "/settings", label: "Configuración", icon: "settings" },
        { path: "/support", label: "Soporte", icon: "help" },
    ];

    const isActive = (path: string) => {
        if (path === "/" && pathname === "/") return true;
        if (path !== "/" && pathname.startsWith(path)) return true;
        return false;
    };

    return (
        <aside className="w-64 flex-shrink-0 flex flex-col bg-slate-900 hidden md:flex">
            {/* Logo */}
            <div className="h-16 flex items-center px-5 border-b border-slate-800">
                <div className="flex items-center gap-3">
                    <div className="bg-primary/25 p-1.5 rounded-lg border border-primary/30">
                        <span className="material-symbols-outlined text-primary text-[22px]">
                            smart_toy
                        </span>
                    </div>
                    <div>
                        <h1 className="text-base font-bold leading-none tracking-tight text-white">
                            RecruitAI
                        </h1>
                        <p className="text-slate-500 text-[10px] font-semibold uppercase tracking-widest mt-0.5">
                            Sistema Central
                        </p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 overflow-y-auto py-5 px-3 space-y-0.5">
                {navItems.map((item) => (
                    <Link
                        key={item.path}
                        href={item.path}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium ${isActive(item.path)
                            ? "bg-primary text-white shadow-lg shadow-primary/20"
                            : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                            }`}
                    >
                        <span className={`material-symbols-outlined text-[20px] ${isActive(item.path) ? "fill" : ""}`}>
                            {item.icon}
                        </span>
                        {item.label}
                    </Link>
                ))}

                {/* System Section */}
                <div className="pt-4 mt-3 border-t border-slate-800">
                    <p className="px-3 text-[10px] font-bold text-slate-600 uppercase tracking-widest mb-2">
                        Sistema
                    </p>
                    {systemItems
                        .filter(item => {
                            if (item.path === '/settings') return user?.role === 'admin';
                            return true;
                        })
                        .map((item) => (
                        <Link
                            key={item.path}
                            href={item.path}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium ${isActive(item.path)
                                ? "bg-primary text-white shadow-lg shadow-primary/20"
                                : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                                }`}
                        >
                            <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                            {item.label}
                        </Link>
                    ))}

                    {/* Logout */}
                    <button
                        onClick={logout}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-400 hover:bg-rose-500/10 hover:text-rose-400 transition-all text-sm font-medium mt-0.5"
                    >
                        <span className="material-symbols-outlined text-[20px]">logout</span>
                        Cerrar Sesión
                    </button>
                </div>
            </nav>

            {/* Session expiry warning */}
            {sessionWarning && (
                <div className="mx-3 mb-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
                    <div className="flex items-start gap-2">
                        <span className="material-symbols-outlined text-[16px] shrink-0 mt-0.5">timer</span>
                        <div className="flex-1">
                            <p className="font-semibold">Sesión por expirar</p>
                            <p className="text-amber-400/70 mt-0.5">Expira en menos de 10 minutos.</p>
                        </div>
                        <button onClick={dismissSessionWarning} className="shrink-0 hover:text-white transition-colors">
                            <span className="material-symbols-outlined text-[14px]">close</span>
                        </button>
                    </div>
                    <button
                        onClick={logout}
                        className="mt-2 w-full py-1.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-xs font-medium transition-colors"
                    >
                        Renovar sesión
                    </button>
                </div>
            )}

            {/* User Profile */}
            <div className="p-4 border-t border-slate-800">
                <div className="flex items-center gap-3">
                    <div className="size-9 rounded-full bg-gradient-to-br from-primary to-indigo-500 flex items-center justify-center text-white text-sm font-bold shrink-0 ring-2 ring-primary/30">
                        {user?.full_name?.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase() || "U"}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-white truncate">
                            {user?.full_name || "Usuario"}
                        </p>
                        <p className="text-xs text-slate-500">
                            {user?.role === "admin" ? "Administrador" : "Reclutador"}
                        </p>
                    </div>
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
