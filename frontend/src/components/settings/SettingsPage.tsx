"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface Setting {
    key: string;
    value: string;
    description?: string;
}

interface ApiKeyStatus {
    provider: string;
    configured: boolean;
    masked_hint?: string;
}

interface SystemSettings {
    settings: Setting[];
    api_keys_status: ApiKeyStatus[];
}

const PROVIDERS = [
    { value: "ollama", label: "Ollama (local, recomendado)", icon: "dns", iconClass: "text-emerald-500" },
    { value: "gemini", label: "Google Gemini (nube)", icon: "cloud", iconClass: "text-blue-500" },
    { value: "openai", label: "OpenAI (nube)", icon: "cloud", iconClass: "text-violet-500" },
];

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [apiKeys, setApiKeys]   = useState<ApiKeyStatus[]>([]);
    const [isLoading, setIsLoading]   = useState(true);
    const [isSaving, setIsSaving]     = useState(false);
    const [error, setError]           = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    useEffect(() => {
        api.get<SystemSettings>("/admin/settings")
            .then(res => {
                const obj: Record<string, string> = {};
                res.data.settings.forEach(s => { obj[s.key] = s.value; });
                setSettings(obj);
                setApiKeys(res.data.api_keys_status);
            })
            .catch(err => setError(err.response?.data?.detail || "Error cargando configuración"))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccessMessage(null);
        try {
            await api.put("/admin/settings", { settings });
            setSuccessMessage("Configuración guardada correctamente");
            setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err: any) {
            setError(err.response?.data?.detail || "Error guardando configuración");
        } finally {
            setIsSaving(false);
        }
    };

    const set = (key: string, value: string) => setSettings(prev => ({ ...prev, [key]: value }));
    const provider = settings["llm_provider"] || "ollama";
    const ollamaKey = apiKeys.find(k => k.provider === "ollama");
    const geminiKey = apiKeys.find(k => k.provider === "gemini");
    const openaiKey = apiKeys.find(k => k.provider === "openai");

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <span className="material-symbols-outlined animate-spin text-primary text-[32px]">progress_activity</span>
            </div>
        );
    }

    return (
        <>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Configuración del Sistema</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Proveedor de IA, modelos, privacidad y retención de datos.
                    </p>
                </div>
            </div>

            <div className="max-w-2xl space-y-6">

                {/* ── Proveedor de IA ─────────────────────────────────────── */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary">smart_toy</span>
                            Proveedor de IA
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Ollama ejecuta los modelos localmente. Gemini y OpenAI requieren API key en el archivo <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">.env</code>.
                        </p>
                    </div>
                    <div className="p-6 space-y-3">
                        {PROVIDERS.map(p => {
                            const isSelected = provider === p.value;
                            const keyStatus = apiKeys.find(k => k.provider === p.value);
                            const isCloud = p.value !== "ollama";
                            const keyOk = !isCloud || keyStatus?.configured;
                            const disabled = isCloud && !keyOk;
                            return (
                                <label
                                    key={p.value}
                                    className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                                        disabled
                                            ? "border-slate-100 dark:border-slate-800 opacity-50 cursor-not-allowed"
                                            : isSelected
                                                ? "border-primary bg-primary/5 dark:bg-primary/10 cursor-pointer"
                                                : "border-slate-200 dark:border-slate-700 hover:border-slate-300 cursor-pointer"
                                    }`}
                                >
                                    <input
                                        type="radio"
                                        name="llm_provider"
                                        value={p.value}
                                        checked={isSelected}
                                        disabled={disabled}
                                        onChange={() => !disabled && set("llm_provider", p.value)}
                                        className="accent-primary"
                                    />
                                    <span className={`material-symbols-outlined text-[20px] ${p.iconClass}`}>{p.icon}</span>
                                    <div className="flex-1">
                                        <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{p.label}</span>
                                        {isCloud && (
                                            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full font-medium ${
                                                keyOk
                                                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                                                    : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                                            }`}>
                                                {keyOk ? `API key: ${keyStatus?.masked_hint ?? "configurada"}` : "Sin API key — configurar en .env"}
                                            </span>
                                        )}
                                        {!isCloud && (
                                            <span className="ml-2 text-xs px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 font-medium">
                                                {ollamaKey?.masked_hint ?? "http://ollama:11434"}
                                            </span>
                                        )}
                                    </div>
                                </label>
                            );
                        })}
                        <p className="text-xs text-slate-400 flex items-start gap-1 pt-1">
                            <span className="material-symbols-outlined text-[14px] mt-0.5">lock</span>
                            Las API keys de proveedores cloud se configuran en el archivo{" "}
                            <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">.env</code>{" "}
                            — no se pueden cambiar desde esta interfaz por seguridad.
                        </p>
                    </div>
                </div>

                {/* ── Modelos Ollama (solo visible si proveedor = ollama) ──── */}
                {provider === "ollama" && (
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <span className="material-symbols-outlined text-emerald-500">dns</span>
                                Modelos Ollama
                            </h2>
                        </div>
                        <div className="p-6 space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Modelo principal (extracción + matching)
                                    </label>
                                    <input
                                        type="text"
                                        value={settings["ollama_model"] || ""}
                                        onChange={e => set("ollama_model", e.target.value)}
                                        placeholder="gemma4:e2b"
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                    />
                                    <p className="text-xs text-slate-400">gemma4:e2b (equilibrado) · gemma4:e4b (mayor calidad, requiere 8GB VRAM)</p>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        URL del servidor Ollama
                                    </label>
                                    <input
                                        type="text"
                                        value={settings["ollama_host"] || ""}
                                        onChange={e => set("ollama_host", e.target.value)}
                                        placeholder="http://ollama:11434"
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                    />
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Modelo de embeddings
                                </label>
                                <input
                                    type="text"
                                    value={settings["embedding_model"] || ""}
                                    onChange={e => set("embedding_model", e.target.value)}
                                    placeholder="nomic-embed-text"
                                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                />
                                <p className="text-xs text-slate-400">Para búsqueda semántica. Predeterminado: nomic-embed-text</p>
                            </div>
                            <p className="text-xs text-slate-400 flex items-center gap-1">
                                <span className="material-symbols-outlined text-[14px]">info</span>
                                Cambiar modelo requiere que el modelo esté descargado en Ollama. Verifica con{" "}
                                <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">docker exec recruitai-ollama ollama list</code>
                            </p>
                        </div>
                    </div>
                )}

                {/* ── Procesamiento de Documentos ─────────────────────────── */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-500">description</span>
                            Procesamiento de Documentos
                        </h2>
                    </div>
                    <div className="p-6 space-y-3">
                        <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                            <span className="material-symbols-outlined text-blue-500 text-[20px]">check_circle</span>
                            <div>
                                <p className="text-sm font-medium text-blue-700 dark:text-blue-300">PyMuPDF · MarkItDown</p>
                                <p className="text-xs text-blue-600 dark:text-blue-400">
                                    PDF con extracción híbrida (tablas + texto) · DOCX con MarkItDown. Sin dependencias externas.
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                            <span className="material-symbols-outlined text-emerald-500 text-[20px]">verified_user</span>
                            <div>
                                <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">Validación de archivos activada</p>
                                <p className="text-xs text-emerald-600 dark:text-emerald-400">
                                    Magic bytes verification — solo se procesan PDF y DOCX auténticos.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* ── Privacidad y Retención ───────────────────────────────── */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-indigo-500">shield</span>
                            Privacidad y Retención de Datos
                        </h2>
                    </div>
                    <div className="p-6 space-y-4">
                        {provider === "ollama" ? (
                            <div className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                                <span className="material-symbols-outlined text-emerald-500 text-[20px]">lock</span>
                                <div>
                                    <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">Datos 100% locales — PII masking innecesario</p>
                                    <p className="text-xs text-emerald-600 dark:text-emerald-400">
                                        Con Ollama los CVs nunca salen del servidor. El enmascaramiento solo aplica con proveedores cloud.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <label className="flex items-start gap-3 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={settings["pii_masking_enabled"] === "true"}
                                    onChange={e => set("pii_masking_enabled", e.target.checked ? "true" : "false")}
                                    className="mt-0.5 w-5 h-5 rounded border-slate-300 text-primary focus:ring-primary"
                                />
                                <div>
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                        Enmascarar datos personales (PII) antes de enviar al LLM
                                    </span>
                                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 font-medium">
                                        Recomendado al usar {provider === "gemini" ? "Gemini" : "OpenAI"} — los CVs se envían a servidores externos.
                                    </p>
                                </div>
                            </label>
                        )}
                        <div className="space-y-1.5">
                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Retención de datos (días)
                            </label>
                            <input
                                type="number"
                                min={30}
                                max={3650}
                                value={settings["data_retention_days"] || "730"}
                                onChange={e => set("data_retention_days", e.target.value)}
                                className="w-40 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                            />
                            <p className="text-xs text-slate-400">Tiempo máximo de almacenamiento de CVs (cumplimiento LPDP Perú). Predeterminado: 730 días (2 años).</p>
                        </div>
                    </div>
                </div>

                {/* ── Stack técnico ─────────────────────────────────────────── */}
                <div className="p-4 bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-slate-400 text-[20px] mt-0.5">info</span>
                        <div>
                            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Stack técnico activo</p>
                            <p className="text-xs text-slate-500 mt-1">
                                {provider === "ollama"
                                    ? `Ollama (${settings["ollama_model"] || "gemma4:e2b"} + ${settings["embedding_model"] || "nomic-embed-text"}) · GPU NVIDIA CUDA · PyMuPDF · Qdrant · PostgreSQL · MinIO · Next.js`
                                    : `${provider.charAt(0).toUpperCase() + provider.slice(1)} (nube) + nomic-embed-text local · PyMuPDF · Qdrant · PostgreSQL · Next.js`
                                }
                            </p>
                            <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 flex items-center gap-1">
                                <span className="material-symbols-outlined text-[13px]">warning</span>
                                Los cambios de proveedor o modelo requieren reiniciar el backend:
                                <code className="ml-1 bg-slate-100 dark:bg-slate-700 px-1 rounded">docker restart recruitai-backend</code>
                            </p>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg text-sm text-rose-700 dark:text-rose-300 flex items-center gap-2">
                        <span className="material-symbols-outlined text-[16px]">error</span>
                        {error}
                    </div>
                )}

                <div className="flex items-center gap-3">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="px-5 py-2 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors text-sm disabled:opacity-50 flex items-center gap-2"
                    >
                        {isSaving && <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>}
                        {isSaving ? "Guardando..." : "Guardar Configuración"}
                    </button>
                    {successMessage && (
                        <span className="text-sm text-emerald-600 font-medium flex items-center gap-1">
                            <span className="material-symbols-outlined text-[16px]">check_circle</span>
                            {successMessage}
                        </span>
                    )}
                </div>
            </div>
        </>
    );
};

export default SettingsPage;
