"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

function SessionExpiredBanner() {
    const searchParams = useSearchParams();
    const sessionExpired = searchParams.get("session") === "expired";

    if (!sessionExpired) return null;

    return (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-sm mb-6">
            <span className="material-symbols-outlined text-[20px] shrink-0">timer_off</span>
            <span>Tu sesión expiró por inactividad. Inicia sesión nuevamente para continuar.</span>
        </div>
    );
}

function LoginForm() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const { login } = useAuth();
    const router = useRouter();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        try {
            await login(email, password);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error al iniciar sesión");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="bg-white dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl p-6 space-y-4 shadow-sm">
                {/* Email */}
                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Correo Electrónico
                    </label>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                            mail
                        </span>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="tu@email.com"
                            required
                            className="w-full pl-10 pr-4 py-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white placeholder-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all"
                        />
                    </div>
                </div>

                {/* Password */}
                <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Contraseña
                    </label>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                            lock
                        </span>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            required
                            className="w-full pl-10 pr-4 py-3 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white placeholder-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all"
                        />
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-sm">
                        <span className="material-symbols-outlined text-[20px]">error</span>
                        {error}
                    </div>
                )}

                {/* Submit Button */}
                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3 px-4 rounded-lg bg-primary text-white font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                    {isLoading ? (
                        <>
                            <span className="material-symbols-outlined animate-spin">progress_activity</span>
                            Iniciando sesión...
                        </>
                    ) : (
                        <>
                            <span className="material-symbols-outlined">login</span>
                            Iniciar Sesión
                        </>
                    )}
                </button>
            </div>

            {/* IT Contact Info - No public registration */}
            <p className="text-center text-slate-500 dark:text-slate-500 text-sm">
                ¿Necesitas acceso? Contacta a TI
            </p>

            {/* Demo Credentials */}
            <div className="mt-6 p-4 rounded-lg bg-slate-100 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-3">
                <p className="text-xs text-slate-500 text-center mb-2">Cuentas de demostración:</p>

                {/* Admin Account */}
                <div className="p-2 rounded bg-white dark:bg-slate-800 border border-emerald-500/30">
                    <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mb-1">👤 Administrador (TI)</p>
                    <div className="flex justify-between text-xs">
                        <span className="text-slate-700 dark:text-slate-300">admin@recruitai.com</span>
                        <span className="text-slate-500 dark:text-slate-400">admin123</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1">Acceso completo + Configuración API</p>
                </div>

                {/* HR Account */}
                <div className="p-2 rounded bg-white dark:bg-slate-800 border border-blue-500/30">
                    <p className="text-xs text-blue-600 dark:text-blue-400 font-medium mb-1">👤 Recursos Humanos</p>
                    <div className="flex justify-between text-xs">
                        <span className="text-slate-700 dark:text-slate-300">rrhh@recruitai.com</span>
                        <span className="text-slate-500 dark:text-slate-400">rrhh123</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1">Solo herramientas de reclutamiento</p>
                </div>
            </div>
        </form>
    );
}

export default function LoginPage() {
    return (
        <div className="min-h-screen bg-slate-50 dark:bg-[#0f172a] flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-3 mb-4">
                        <div className="bg-primary/20 p-2 rounded-xl">
                            <span className="material-symbols-outlined text-primary text-[32px]">smart_toy</span>
                        </div>
                        <div className="text-left">
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">RecruitAI</h1>
                            <p className="text-slate-500 text-sm">Sistema Central</p>
                        </div>
                    </div>
                    <p className="text-slate-500 dark:text-slate-400">Inicia sesión para continuar</p>
                </div>

                {/* Session expired banner — reads ?session=expired from URL */}
                <Suspense fallback={null}>
                    <SessionExpiredBanner />
                </Suspense>

                <Suspense fallback={null}>
                    <LoginForm />
                </Suspense>
            </div>
        </div>
    );
}
