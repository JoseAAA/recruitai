"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function RegisterPage() {
    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const { register } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (password !== confirmPassword) {
            setError("Las contraseñas no coinciden");
            return;
        }

        if (password.length < 6) {
            setError("La contraseña debe tener al menos 6 caracteres");
            return;
        }

        setIsLoading(true);

        try {
            await register(email, password, fullName);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error al registrarse");
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
                    <p className="text-slate-400">Crea tu cuenta para comenzar</p>
                </div>

                {/* Register Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-6 space-y-4">
                        {/* Full Name */}
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Nombre Completo
                            </label>
                            <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                                    person
                                </span>
                                <input
                                    type="text"
                                    value={fullName}
                                    onChange={(e) => setFullName(e.target.value)}
                                    placeholder="Tu nombre completo"
                                    required
                                    className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-[#334155] rounded-lg text-white placeholder-slate-500 focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all"
                                />
                            </div>
                        </div>

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
                                    placeholder="Mínimo 6 caracteres"
                                    required
                                    className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-[#334155] rounded-lg text-white placeholder-slate-500 focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all"
                                />
                            </div>
                        </div>

                        {/* Confirm Password */}
                        <div>
                            <label className="block text-sm font-medium text-slate-300 mb-2">
                                Confirmar Contraseña
                            </label>
                            <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[20px]">
                                    lock
                                </span>
                                <input
                                    type="password"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    placeholder="Repite tu contraseña"
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
                                    Registrando...
                                </>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined">person_add</span>
                                    Crear Cuenta
                                </>
                            )}
                        </button>
                    </div>

                    {/* Login Link */}
                    <p className="text-center text-slate-400 text-sm">
                        ¿Ya tienes cuenta?{" "}
                        <Link href="/login" className="text-[#135bec] hover:underline">
                            Inicia sesión
                        </Link>
                    </p>
                </form>
            </div>
        </div>
    );
}
