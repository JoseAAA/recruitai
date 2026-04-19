"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAI } from "@/lib/ai";

function useTheme() {
    const [isDark, setIsDark] = useState(true);

    useEffect(() => {
        const stored = localStorage.getItem("theme");
        setIsDark(stored === null || stored === "dark");
    }, []);

    const toggle = () => {
        const next = !isDark;
        setIsDark(next);
        localStorage.setItem("theme", next ? "dark" : "light");
        document.documentElement.classList.toggle("dark", next);
    };

    return { isDark, toggle };
}

const Header: React.FC = () => {
    const { config, isAvailable } = useAI();
    const { isDark, toggle } = useTheme();

    return (
        <header className="h-16 flex items-center justify-end px-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 backdrop-blur-sm flex-shrink-0 sticky top-0 z-30 gap-2.5">
            {/* AI Status Indicator */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                <span className={`relative flex h-2 w-2 ${isAvailable ? "" : "opacity-50"}`}>
                    {isAvailable && (
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    )}
                    <span className={`relative inline-flex rounded-full h-2 w-2 ${isAvailable ? "bg-emerald-500" : "bg-slate-400"}`}></span>
                </span>
                <span className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-400 tracking-wider">
                    {config?.provider ? config.provider.toUpperCase() : "IA"}
                </span>
            </div>

            {/* Theme Toggle */}
            <button
                onClick={toggle}
                title={isDark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
                className="flex items-center justify-center w-9 h-9 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
            >
                <span className="material-symbols-outlined text-[18px]">
                    {isDark ? "light_mode" : "dark_mode"}
                </span>
            </button>

            {/* New Vacancy Button */}
            <Link
                href="/jobs/new"
                className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-primary rounded-xl hover:bg-primary/90 transition-colors shadow-sm shadow-primary/30"
            >
                <span className="material-symbols-outlined text-[18px]">add</span>
                <span className="hidden sm:inline">Nueva Vacante</span>
            </Link>
        </header>
    );
};

export default Header;
