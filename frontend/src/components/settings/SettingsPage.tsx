"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import UsersSection from "./UsersSection";

interface Setting {
    key: string;
    value: string;
    description?: string;
    // True si el campo vive en .env y la UI debe mostrarlo read-only.
    source_env?: boolean;
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
    {
        value: "ollama",
        label: "Ollama (local, recomendado)",
        sublabel: "100% on-premise, datos nunca salen. Requiere GPU NVIDIA.",
        icon: "dns",
        iconClass: "text-emerald-500",
    },
    {
        value: "groq",
        label: "Groq (nube, ultrarrápido)",
        sublabel: "5-10× más rápido que OpenAI. Free tier disponible.",
        icon: "bolt",
        iconClass: "text-amber-500",
    },
    {
        value: "gemini",
        label: "Google Gemini (nube)",
        sublabel: "Free tier 1.5k req/día. Buena relación calidad/precio.",
        icon: "cloud",
        iconClass: "text-blue-500",
    },
    {
        value: "openai",
        label: "OpenAI (nube)",
        sublabel: "Máxima calidad. Sin free tier.",
        icon: "cloud",
        iconClass: "text-violet-500",
    },
];

const PROVIDER_MODEL_KEY: Record<string, string> = {
    ollama: "ollama_model",
    groq: "groq_model",
    gemini: "gemini_model",
    openai: "openai_model",
};

const PROVIDER_MODEL_HINTS: Record<string, string> = {
    ollama: "gemma3:4b (recomendado) · qwen3:4b · llama3.2:3b",
    groq: "llama-3.3-70b-versatile (recomendado) · ver console.groq.com/docs/models",
    gemini: "gemini-2.5-flash (recomendado) · gemini-2.5-flash-lite",
    openai: "gpt-4o-mini (recomendado) · gpt-4o",
};

const SettingsPage: React.FC = () => {
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [envBacked, setEnvBacked] = useState<Set<string>>(new Set());
    const [apiKeys, setApiKeys]   = useState<ApiKeyStatus[]>([]);
    const [isLoading, setIsLoading]   = useState(true);
    const [isSaving, setIsSaving]     = useState(false);
    const [error, setError]           = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    useEffect(() => {
        api.get<SystemSettings>("/admin/settings")
            .then(res => {
                const obj: Record<string, string> = {};
                const envKeys = new Set<string>();
                res.data.settings.forEach(s => {
                    obj[s.key] = s.value;
                    if (s.source_env) envKeys.add(s.key);
                });
                setSettings(obj);
                setEnvBacked(envKeys);
                setApiKeys(res.data.api_keys_status);
            })
            .catch(err => setError(err.response?.data?.detail || "Error cargando configuración"))
            .finally(() => setIsLoading(false));
    }, []);

    // Badge que se renderiza al lado del label cuando el campo viene de .env
    const envBadge = (
        <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
            <span className="material-symbols-outlined text-[12px]">lock</span>
            .env
        </span>
    );

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccessMessage(null);
        try {
            // Solo enviamos los campos editables (no los .env). El backend
            // los rechazaría con 400 si los incluyéramos.
            const editable: Record<string, string> = {};
            Object.entries(settings).forEach(([k, v]) => {
                if (!envBacked.has(k)) editable[k] = v;
            });
            await api.put("/admin/settings", { settings: editable });
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
                        Estado actual: <span className="font-semibold text-slate-700 dark:text-slate-200">{provider.toUpperCase()}</span>{" "}
                        para generación · <span className="font-semibold text-slate-700 dark:text-slate-200">TEI</span> para embeddings.
                        {" "}Para cambiar proveedor o modelo, edita <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded text-xs">.env</code> y reinicia el backend.
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
                            {envBacked.has("llm_provider") && envBadge}
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Modelo actualmente activo: <strong className="text-slate-700 dark:text-slate-300">{provider}</strong>.{" "}
                            {envBacked.has("llm_provider")
                                ? <>Para cambiar el proveedor edita <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">LLM_PROVIDER</code> en el archivo <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">.env</code> y reinicia el backend.</>
                                : <>Ollama ejecuta los modelos localmente. Gemini/Groq/OpenAI requieren API key en el archivo .env.</>
                            }
                        </p>
                    </div>
                    <div className="p-6 space-y-3">
                        {PROVIDERS.map(p => {
                            const isSelected = provider === p.value;
                            const keyStatus = apiKeys.find(k => k.provider === p.value);
                            const isCloud = p.value !== "ollama";
                            const keyOk = !isCloud || keyStatus?.configured;
                            // Si el proveedor viene de .env, los radios son solo informativos.
                            const readOnly = envBacked.has("llm_provider");
                            const disabled = readOnly || (isCloud && !keyOk);
                            return (
                                <label
                                    key={p.value}
                                    className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
                                        disabled && !isSelected
                                            ? "border-slate-100 dark:border-slate-800 opacity-50 cursor-not-allowed"
                                            : isSelected
                                                ? "border-primary bg-primary/5 dark:bg-primary/10"
                                                : "border-slate-200 dark:border-slate-700 hover:border-slate-300 cursor-pointer"
                                    } ${readOnly ? "cursor-default" : ""}`}
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
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{p.label}</span>
                                            {isSelected && (
                                                <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
                                                    Activo
                                                </span>
                                            )}
                                            {isCloud && keyStatus?.configured && (
                                                <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                                                    API key: {keyStatus.masked_hint}
                                                </span>
                                            )}
                                            {isCloud && !keyStatus?.configured && (
                                                <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                                                    Sin API key — configurar en .env
                                                </span>
                                            )}
                                        </div>
                                        {p.sublabel && (
                                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{p.sublabel}</p>
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

                {/* ── Modelo del proveedor activo ──────────────────────────── */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary">memory</span>
                            Modelo de Generación ({provider.charAt(0).toUpperCase() + provider.slice(1)})
                            {envBacked.has(PROVIDER_MODEL_KEY[provider]) && envBadge}
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Modelo que extrae datos de CVs y evalúa candidatos vs vacantes.
                        </p>
                    </div>
                    <div className="p-6 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Modelo (extracción + matching)
                                </label>
                                <input
                                    type="text"
                                    value={settings[PROVIDER_MODEL_KEY[provider]] || ""}
                                    onChange={e => set(PROVIDER_MODEL_KEY[provider], e.target.value)}
                                    readOnly={envBacked.has(PROVIDER_MODEL_KEY[provider])}
                                    placeholder={PROVIDER_MODEL_HINTS[provider]?.split(" · ")[0]}
                                    className={`w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none ${
                                        envBacked.has(PROVIDER_MODEL_KEY[provider])
                                            ? "bg-slate-50 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                            : "bg-white dark:bg-slate-900 focus:ring-2 focus:ring-primary"
                                    }`}
                                />
                                <p className="text-xs text-slate-400">{PROVIDER_MODEL_HINTS[provider]}</p>
                            </div>
                            {provider === "ollama" && (
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        URL del servidor Ollama
                                    </label>
                                    <input
                                        type="text"
                                        value={settings["ollama_host"] || ""}
                                        onChange={e => set("ollama_host", e.target.value)}
                                        readOnly={envBacked.has("ollama_host")}
                                        placeholder="http://ollama:11434"
                                        className={`w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none ${
                                            envBacked.has("ollama_host")
                                                ? "bg-slate-50 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                                : "bg-white dark:bg-slate-900 focus:ring-2 focus:ring-primary"
                                        }`}
                                    />
                                </div>
                            )}
                        </div>
                        {envBacked.has(PROVIDER_MODEL_KEY[provider]) ? (
                            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-start gap-1">
                                <span className="material-symbols-outlined text-[14px] mt-0.5">lock</span>
                                Para cambiar este modelo edita{" "}
                                <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">
                                    {provider.toUpperCase()}_MODEL
                                </code>{" "}
                                en <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">.env</code> y reinicia el backend.
                            </p>
                        ) : provider === "ollama" ? (
                            <p className="text-xs text-slate-400 flex items-center gap-1">
                                <span className="material-symbols-outlined text-[14px]">info</span>
                                Cambiar modelo requiere que esté descargado en Ollama. Verifica con{" "}
                                <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">docker exec recruitai-ollama ollama list</code>
                            </p>
                        ) : null}
                    </div>
                </div>

                {/* ── Embeddings (siempre activo, INDEPENDIENTE del LLM) ───── */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-emerald-500">manage_search</span>
                            Búsqueda Semántica (Embeddings)
                            {envBacked.has("embedding_model") && envBadge}
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Servicio dedicado que convierte texto en vectores para la búsqueda inteligente.
                            Corre <strong>siempre</strong>, independiente del proveedor de IA elegido.
                        </p>
                    </div>
                    <div className="p-6 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Modelo de embeddings
                                </label>
                                <input
                                    type="text"
                                    value={settings["embedding_model"] || ""}
                                    onChange={e => set("embedding_model", e.target.value)}
                                    readOnly={envBacked.has("embedding_model")}
                                    placeholder="Snowflake/snowflake-arctic-embed-m-v2.0"
                                    className={`w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none ${
                                        envBacked.has("embedding_model")
                                            ? "bg-slate-50 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                            : "bg-white dark:bg-slate-900 focus:ring-2 focus:ring-primary"
                                    }`}
                                />
                                <p className="text-xs text-slate-400">
                                    Multilingüe ES/EN, 768 dim. Cambiar a un modelo con dimensión distinta requiere re-indexar Qdrant.
                                </p>
                            </div>
                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    URL del servicio TEI
                                </label>
                                <input
                                    type="text"
                                    value={settings["embeddings_host"] || ""}
                                    onChange={e => set("embeddings_host", e.target.value)}
                                    readOnly={envBacked.has("embeddings_host")}
                                    placeholder="http://embeddings:8080"
                                    className={`w-full px-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none ${
                                        envBacked.has("embeddings_host")
                                            ? "bg-slate-50 dark:bg-slate-900/60 text-slate-500 dark:text-slate-400 cursor-not-allowed"
                                            : "bg-white dark:bg-slate-900 focus:ring-2 focus:ring-primary"
                                    }`}
                                />
                            </div>
                        </div>
                        <div className="flex items-start gap-2 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                            <span className="material-symbols-outlined text-emerald-500 text-[18px] mt-0.5">verified</span>
                            <p className="text-xs text-emerald-700 dark:text-emerald-300">
                                <strong>Embeddings independientes del LLM.</strong> Puedes apagar Ollama y usar
                                Groq/Gemini/OpenAI para la generación sin perder la búsqueda semántica.
                            </p>
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
                        <p className="text-xs text-slate-500 mt-1">
                            Cumplimiento LPDP Perú (Ley 29733).
                        </p>
                    </div>
                    <div className="p-6 space-y-4">
                        {/* Estado actual de PII masking (informativo, no editable — viene de .env) */}
                        {provider === "ollama" ? (
                            <div className="flex items-start gap-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                                <span className="material-symbols-outlined text-emerald-500 text-[20px] mt-0.5">lock</span>
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
                                        Datos 100% locales — sin riesgo de fuga
                                    </p>
                                    <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">
                                        Con Ollama los CVs nunca salen del servidor. El enmascaramiento de PII no se aplica
                                        porque no hace falta.
                                    </p>
                                </div>
                            </div>
                        ) : (
                            <div className="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                                <span className="material-symbols-outlined text-blue-500 text-[20px] mt-0.5">shield</span>
                                <div className="flex-1">
                                    <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
                                        PII masking activado automáticamente
                                    </p>
                                    <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">
                                        Los CVs van a un servidor externo ({provider}). El backend enmascara nombres,
                                        emails, teléfonos y DNIs antes de enviarlos al LLM y los restaura al recibir
                                        la respuesta. Tu cumples LPDP Perú sin esfuerzo manual.
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Único campo realmente editable: retención de datos */}
                        <div className="pt-4 border-t border-slate-100 dark:border-slate-700/50 space-y-1.5">
                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Retención de datos (días) — editable
                            </label>
                            <input
                                type="number"
                                min={30}
                                max={3650}
                                value={settings["data_retention_days"] || "730"}
                                onChange={e => set("data_retention_days", e.target.value)}
                                className="w-40 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                            />
                            <p className="text-xs text-slate-400">
                                Tiempo máximo de almacenamiento de CVs antes de eliminación automática.
                                Recomendado: 730 días (2 años) según LPDP Perú.
                            </p>
                        </div>
                    </div>
                </div>

                {/* ── Usuarios y Contraseñas (solo admin) ──────────────────── */}
                <UsersSection />

                {/* ── Stack técnico ─────────────────────────────────────────── */}
                <div className="p-4 bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 rounded-xl">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-slate-400 text-[20px] mt-0.5">info</span>
                        <div className="flex-1">
                            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Stack técnico activo</p>
                            <ul className="text-xs text-slate-500 mt-2 space-y-1">
                                <li>
                                    <strong>Generación:</strong>{" "}
                                    {provider === "ollama" && `Ollama local (${settings["ollama_model"] || "gemma3:4b"}) · GPU NVIDIA`}
                                    {provider === "groq" && `Groq Cloud (${settings["groq_model"] || "llama-3.3-70b-versatile"}) · 5-10× más rápido`}
                                    {provider === "gemini" && `Google Gemini (${settings["gemini_model"] || "gemini-2.5-flash"}) · free tier ~1.5k req/día`}
                                    {provider === "openai" && `OpenAI (${settings["openai_model"] || "gpt-4o-mini"})`}
                                </li>
                                <li>
                                    <strong>Embeddings:</strong>{" "}
                                    {(settings["embedding_model"] || "Snowflake/snowflake-arctic-embed-m-v2.0")} · TEI dedicado · 768 dim
                                </li>
                                <li>
                                    <strong>Documentos:</strong> PyMuPDF (PDF híbrido) · MarkItDown (DOCX)
                                </li>
                                <li>
                                    <strong>Almacenamiento:</strong> PostgreSQL · Qdrant (vectores) · MinIO (archivos)
                                </li>
                                <li>
                                    <strong>Frontend:</strong> Next.js 14 + Tailwind
                                </li>
                            </ul>
                            <p className="text-xs text-amber-600 dark:text-amber-400 mt-3 flex items-center gap-1">
                                <span className="material-symbols-outlined text-[13px]">warning</span>
                                Cambios de proveedor o modelo requieren reiniciar el backend:
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

                {/* Solo se guarda lo realmente editable. Los campos .env-backed
                    quedan read-only; ese filtrado lo hace handleSave(). */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="px-5 py-2 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors text-sm disabled:opacity-50 flex items-center gap-2"
                    >
                        {isSaving && <span className="material-symbols-outlined text-[16px] animate-spin">progress_activity</span>}
                        {isSaving ? "Guardando..." : "Guardar cambios"}
                    </button>
                    <span className="text-xs text-slate-400">
                        Solo se guarda lo editable (retención de datos). El resto vive en <code className="bg-slate-100 dark:bg-slate-700 px-1 rounded">.env</code>.
                    </span>
                    {successMessage && (
                        <span className="text-sm text-emerald-600 font-medium flex items-center gap-1 ml-auto">
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
