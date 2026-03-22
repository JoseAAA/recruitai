"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
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
        <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-3 mb-4">
                        <div className="bg-[#135bec]/20 p-2 rounded-xl">
                            <span className="material-symbols-outlined text-[#135bec] text-[32px]">smart_toy</span>
                        </div>
                        <div className="text-left">
                            <h1 className="text-2xl font-bold text-white">RecruitAI</h1>
                            <p className="text-slate-500 text-sm">Sistema Central</p>
                        </div>
                    </div>
                    <p className="text-slate-400">Inicia sesión para continuar</p>
                </div>

                {/* Login Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-6 space-y-4">
                        {/* Email */}
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
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
                                    className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-[#334155] rounded-lg text-white placeholder-slate-500 focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all"
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
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
                                    className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-[#334155] rounded-lg text-white placeholder-slate-500 focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all"
                                />
                            </div>
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
                                <span className="material-symbols-outlined text-[20px]">error</span>
                                {error}
                            </div>
                        )}

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full py-3 px-4 rounded-lg bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
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
                    <p className="text-center text-slate-500 text-sm">
                        ¿Necesitas acceso? Contacta a TI
                    </p>

                    {/* Demo Credentials */}
                    <div className="mt-6 p-4 rounded-lg bg-slate-800/50 border border-slate-700 space-y-3">
                        <p className="text-xs text-slate-400 text-center mb-2">Cuentas de demostración:</p>

                        {/* Admin Account */}
                        <div className="p-2 rounded bg-slate-800 border border-emerald-500/30">
                            <p className="text-xs text-emerald-400 font-medium mb-1">👤 Administrador (TI)</p>
                            <div className="flex justify-between text-xs">
                                <span className="text-slate-300">admin@recruitai.com</span>
                                <span className="text-slate-400">admin123</span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1">Acceso completo + Configuración API</p>
                        </div>

                        {/* HR Account */}
                        <div className="p-2 rounded bg-slate-800 border border-blue-500/30">
                            <p className="text-xs text-blue-400 font-medium mb-1">👤 Recursos Humanos</p>
                            <div className="flex justify-between text-xs">
                                <span className="text-slate-300">rrhh@recruitai.com</span>
                                <span className="text-slate-400">rrhh123</span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1">Solo herramientas de reclutamiento</p>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
}
