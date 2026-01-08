"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const Sidebar: React.FC = () => {
    const pathname = usePathname();
    const { user, logout } = useAuth();

    const navItems = [
        { path: "/", label: "Panel de Control", icon: "dashboard" },
        { path: "/candidates", label: "Candidatos", icon: "group" },
        { path: "/jobs", label: "Empleos", icon: "work" },
        { path: "/data", label: "Centro de Datos", icon: "database" },
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
        <aside className="w-64 flex-shrink-0 flex flex-col border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0f172a] hidden md:flex">
            {/* Logo */}
            <div className="h-16 flex items-center px-6 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-3">
                    <div className="bg-primary/20 p-1.5 rounded-lg">
                        <span className="material-symbols-outlined text-primary text-[24px]">
                            smart_toy
                        </span>
                    </div>
                    <div>
                        <h1 className="text-base font-bold leading-none tracking-tight">
                            RecruitAI
                        </h1>
                        <p className="text-slate-500 text-xs font-medium uppercase tracking-widest">
                            Sistema Central
                        </p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1">
                {navItems.map((item) => (
                    <Link
                        key={item.path}
                        href={item.path}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive(item.path)
                            ? "bg-primary/10 text-primary"
                            : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
                            }`}
                    >
                        <span
                            className={`material-symbols-outlined ${isActive(item.path) ? "fill" : ""
                                }`}
                        >
                            {item.icon}
                        </span>
                        <span className="text-sm font-medium">{item.label}</span>
                    </Link>
                ))}

                {/* System Section */}
                <div className="pt-4 mt-4 border-t border-slate-200 dark:border-slate-800">
                    <p className="px-3 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                        Sistema
                    </p>
                    {systemItems.map((item) => (
                        <Link
                            key={item.path}
                            href={item.path}
                            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive(item.path)
                                ? "bg-primary/10 text-primary"
                                : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white"
                                }`}
                        >
                            <span className="material-symbols-outlined">{item.icon}</span>
                            <span className="text-sm font-medium">{item.label}</span>
                        </Link>
                    ))}

                    {/* Logout Button */}
                    <button
                        onClick={logout}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 hover:text-rose-600 dark:hover:text-rose-400 transition-colors"
                    >
                        <span className="material-symbols-outlined">logout</span>
                        <span className="text-sm font-medium">Cerrar Sesión</span>
                    </button>
                </div>
            </nav>

            {/* User Profile */}
            <div className="p-4 border-t border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-3">
                    <div className="size-9 rounded-full bg-gradient-to-br from-primary to-indigo-600 flex items-center justify-center text-white text-sm font-semibold">
                        {user?.full_name?.split(" ").map((n) => n[0]).join("") || "U"}
                    </div>
                    <div className="flex flex-col">
                        <p className="text-sm font-semibold dark:text-white">
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
