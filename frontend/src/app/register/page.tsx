"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Registration is disabled for public access.
 * Only IT administrators can create new users via the backend API.
 * 
 * This page redirects to login with a message.
 */
export default function RegisterPage() {
    const router = useRouter();

    useEffect(() => {
        // Redirect to login - registration is disabled
        router.replace('/login');
    }, [router]);

    return (
        <div className="min-h-screen bg-[#0f172a] flex items-center justify-center p-4">
            <div className="w-full max-w-md text-center">
                <div className="bg-[#1e293b] border border-[#334155] rounded-xl p-6">
                    <span className="material-symbols-outlined text-amber-400 text-[48px] mb-4">
                        admin_panel_settings
                    </span>
                    <h2 className="text-xl font-bold text-white mb-2">
                        Registro Deshabilitado
                    </h2>
                    <p className="text-slate-400 mb-4">
                        El registro público está deshabilitado por seguridad.
                        <br />
                        Solo el equipo de TI puede crear nuevas cuentas.
                    </p>
                    <p className="text-slate-500 text-sm">
                        Redirigiendo al login...
                    </p>
                </div>
            </div>
        </div>
    );
}
