"use client";

import { useState } from "react";
import { useAI } from "@/lib/ai";
import { AIProviderType } from "@/lib/ai/types";

const SettingsPage: React.FC = () => {
    const { config, setProviderType, updateConfig, testConnection, isLoading, isAvailable, error } = useAI();
    const [apiKey, setApiKey] = useState(config.apiKey || "");
    const [model, setModel] = useState(config.model);
    const [baseUrl, setBaseUrl] = useState(config.baseUrl || "");
    const [testResult, setTestResult] = useState<string | null>(null);

    const handleProviderChange = (type: AIProviderType) => {
        setProviderType(type);
        setApiKey("");
        setTestResult(null);
    };

    const handleSaveConfig = () => {
        updateConfig({ apiKey, model, baseUrl });
        setTestResult(null);
    };

    const handleTestConnection = async () => {
        const success = await testConnection();
        setTestResult(success ? "✅ Conexión exitosa" : "❌ Error de conexión");
    };

    const providers: { type: AIProviderType; name: string; description: string; icon: string }[] = [
        {
            type: "ollama",
            name: "Ollama (Local)",
            description: "IA local gratuita. Requiere Ollama instalado.",
            icon: "dns",
        },
        {
            type: "openai",
            name: "OpenAI",
            description: "GPT-4o y variantes. API de pago.",
            icon: "psychology",
        },
        {
            type: "gemini",
            name: "Google Gemini",
            description: "Gemini 1.5. Tier gratuito disponible.",
            icon: "auto_awesome",
        },
    ];

    return (
        <>
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Configuración del Sistema
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Administra las preferencias de IA, integraciones y seguridad.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* AI Provider Selection */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <span className="material-symbols-outlined text-indigo-500">smart_toy</span>
                                Proveedor de IA
                            </h2>
                        </div>
                        <div className="p-6 space-y-6">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                {providers.map((p) => (
                                    <button
                                        key={p.type}
                                        onClick={() => handleProviderChange(p.type)}
                                        className={`p-4 rounded-xl border-2 text-left transition-all ${config.type === p.type
                                                ? "border-primary bg-primary/5 dark:bg-primary/10"
                                                : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                                            }`}
                                    >
                                        <span
                                            className={`material-symbols-outlined text-[28px] mb-2 ${config.type === p.type
                                                    ? "text-primary"
                                                    : "text-slate-400"
                                                }`}
                                        >
                                            {p.icon}
                                        </span>
                                        <h3 className="font-bold text-slate-900 dark:text-white text-sm">
                                            {p.name}
                                        </h3>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                            {p.description}
                                        </p>
                                    </button>
                                ))}
                            </div>

                            {/* Provider Configuration */}
                            <div className="pt-4 border-t border-slate-100 dark:border-slate-700 space-y-4">
                                {config.type === "ollama" && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-1.5">
                                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase">
                                                URL del Servidor
                                            </label>
                                            <input
                                                type="text"
                                                value={baseUrl}
                                                onChange={(e) => setBaseUrl(e.target.value)}
                                                placeholder="http://localhost:11434"
                                                className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase">
                                                Modelo
                                            </label>
                                            <select
                                                value={model}
                                                onChange={(e) => setModel(e.target.value)}
                                                className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                            >
                                                <option value="mistral-nemo">mistral-nemo</option>
                                                <option value="llama3.1">llama3.1</option>
                                                <option value="gemma2">gemma2</option>
                                                <option value="phi3">phi3</option>
                                            </select>
                                        </div>
                                    </div>
                                )}

                                {(config.type === "openai" || config.type === "gemini") && (
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div className="space-y-1.5">
                                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase">
                                                API Key
                                            </label>
                                            <input
                                                type="password"
                                                value={apiKey}
                                                onChange={(e) => setApiKey(e.target.value)}
                                                placeholder={config.type === "openai" ? "sk-..." : "AI..."}
                                                className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase">
                                                Modelo
                                            </label>
                                            <select
                                                value={model}
                                                onChange={(e) => setModel(e.target.value)}
                                                className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                            >
                                                {config.type === "openai" ? (
                                                    <>
                                                        <option value="gpt-4o-mini">gpt-4o-mini</option>
                                                        <option value="gpt-4o">gpt-4o</option>
                                                        <option value="gpt-4-turbo">gpt-4-turbo</option>
                                                    </>
                                                ) : (
                                                    <>
                                                        <option value="gemini-1.5-flash">gemini-1.5-flash</option>
                                                        <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                                                        <option value="gemini-2.0-flash">gemini-2.0-flash</option>
                                                    </>
                                                )}
                                            </select>
                                        </div>
                                    </div>
                                )}

                                <div className="flex items-center gap-3 pt-2">
                                    <button
                                        onClick={handleSaveConfig}
                                        className="px-4 py-2 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors text-sm"
                                    >
                                        Guardar Configuración
                                    </button>
                                    <button
                                        onClick={handleTestConnection}
                                        disabled={isLoading}
                                        className="px-4 py-2 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-sm disabled:opacity-50"
                                    >
                                        {isLoading ? "Probando..." : "Probar Conexión"}
                                    </button>
                                    {testResult && (
                                        <span className="text-sm font-medium">{testResult}</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Status Panel */}
                <div className="space-y-6">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">
                            Estado del Sistema
                        </h3>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-700 dark:text-slate-300">
                                    Proveedor IA
                                </span>
                                <div className="flex items-center gap-2">
                                    <span
                                        className={`h-2 w-2 rounded-full ${isAvailable ? "bg-emerald-500" : "bg-rose-500"
                                            }`}
                                    ></span>
                                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                                        {isAvailable ? "Conectado" : "Desconectado"}
                                    </span>
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-700 dark:text-slate-300">
                                    Base de Datos
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                                        PostgreSQL
                                    </span>
                                </div>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-slate-700 dark:text-slate-300">
                                    Vector DB
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                                    <span className="text-sm font-medium text-slate-900 dark:text-white">
                                        Qdrant
                                    </span>
                                </div>
                            </div>
                        </div>
                        {error && (
                            <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg text-sm text-rose-700 dark:text-rose-300">
                                {error}
                            </div>
                        )}
                    </div>

                    <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800 rounded-xl p-5">
                        <h3 className="text-sm font-bold text-indigo-900 dark:text-indigo-200 mb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px]">lightbulb</span>
                            Consejo
                        </h3>
                        <p className="text-xs text-indigo-700 dark:text-indigo-300 leading-relaxed">
                            Para usar Ollama local, asegúrate de tener instalado el servidor y
                            al menos un modelo descargado con{" "}
                            <code className="bg-indigo-100 dark:bg-indigo-800 px-1 rounded">
                                ollama pull mistral-nemo
                            </code>
                        </p>
                    </div>
                </div>
            </div>
        </>
    );
};

export default SettingsPage;
