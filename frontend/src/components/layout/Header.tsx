"use client";

import { useState } from "react";
import Link from "next/link";
import { useAI } from "@/lib/ai";

const Header: React.FC = () => {
    const [searchQuery, setSearchQuery] = useState("");
    const { config, isAvailable } = useAI();

    return (
        <header className="h-16 flex items-center justify-between px-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0f172a] flex-shrink-0">
            {/* Search Bar */}
            <div className="flex items-center flex-1 max-w-xl">
                <div className="relative w-full">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                        search
                    </span>
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Buscar candidatos, empleos o etiquetas..."
                        className="w-full pl-10 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all"
                    />
                </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-3 ml-6">
                {/* AI Status Indicator */}
                <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                    <span
                        className={`relative flex h-2 w-2 ${isAvailable ? "" : "opacity-50"
                            }`}
                    >
                        {isAvailable && (
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        )}
                        <span
                            className={`relative inline-flex rounded-full h-2 w-2 ${isAvailable ? "bg-emerald-500" : "bg-slate-400"
                                }`}
                        ></span>
                    </span>
                    <span className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-400">
                        {config.type === "ollama" ? "Ollama" : config.type === "openai" ? "OpenAI" : "Gemini"}
                    </span>
                </div>

                {/* Notifications */}
                <button className="relative p-2 text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                    <span className="material-symbols-outlined">notifications</span>
                    <span className="absolute top-1.5 right-1.5 size-2 bg-rose-500 rounded-full border-2 border-white dark:border-[#0f172a]"></span>
                </button>

                {/* Messages */}
                <button className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
                    <span className="material-symbols-outlined">chat</span>
                </button>

                {/* Divider */}
                <div className="h-6 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

                {/* New Vacancy Button */}
                <Link
                    href="/jobs/new"
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors shadow-sm"
                >
                    <span className="material-symbols-outlined text-[18px]">add</span>
                    <span className="hidden sm:inline">Nueva Vacante</span>
                </Link>
            </div>
        </header>
    );
};

export default Header;
