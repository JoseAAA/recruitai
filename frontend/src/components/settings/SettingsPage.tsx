"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

interface Setting {
    key: string;
    value: string;
    description?: string;
}

interface SystemSettings {
    settings: Setting[];
    api_keys_status: { provider: string; configured: boolean }[];
}

const SettingsPage: React.FC = () => {
    const { token } = useAuth();
    const [settings, setSettings] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        const loadSettings = async () => {
            if (!token) return;

            try {
                const response = await fetch(`${API_BASE}/api/admin/settings`, {
                    headers: { 'Authorization': `Bearer ${token}` },
                });

                if (!response.ok) throw new Error('Error cargando configuración');

                const data: SystemSettings = await response.json();
                const settingsObj: Record<string, string> = {};
                data.settings.forEach(s => { settingsObj[s.key] = s.value; });
                setSettings(settingsObj);
                setError(null);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setIsLoading(false);
            }
        };

        loadSettings();
    }, [token, API_BASE]);

    const handleSave = async () => {
        setIsSaving(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const response = await fetch(`${API_BASE}/api/admin/settings`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ settings }),
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Error guardando configuración');
            }

            setSuccessMessage('Configuración guardada correctamente');
            setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-slate-500">Cargando configuración...</div>
            </div>
        );
    }

    return (
        <>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Configuración del Sistema
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Modelos de IA, privacidad y parámetros del sistema.
                    </p>
                </div>
            </div>

            <div className="max-w-2xl space-y-6">
                {/* Ollama — Motor de IA */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-emerald-500">dns</span>
                            Motor de IA — Ollama (Local + GPU)
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Ejecuta IA localmente con aceleración GPU. Sin API keys, sin datos enviados a la nube.
                        </p>
                    </div>
                    <div className="p-6 space-y-4">
                        {/* Ollama Status */}
                        <div className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                            <span className="relative flex h-2.5 w-2.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                            </span>
                            <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
                                Ollama activo — GPU NVIDIA (CUDA)
                            </span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Modelo de extracción y matching
                                </label>
                                <input
                                    type="text"
                                    value={settings['ollama_model'] || ''}
                                    onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                                    placeholder="gemma3:4b"
                                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                />
                                <p className="text-xs text-slate-400">
                                    Recomendados: gemma3:4b (equilibrado) · gemma3:12b (máxima calidad)
                                </p>
                            </div>

                            <div className="space-y-1.5">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    URL del servidor Ollama
                                </label>
                                <input
                                    type="text"
                                    value={settings['ollama_host'] || ''}
                                    onChange={(e) => setSettings({ ...settings, ollama_host: e.target.value })}
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
                                value={settings['embedding_model'] || ''}
                                onChange={(e) => setSettings({ ...settings, embedding_model: e.target.value })}
                                placeholder="nomic-embed-text"
                                className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                            />
                            <p className="text-xs text-slate-400">
                                Para búsqueda semántica de candidatos. Predeterminado: nomic-embed-text
                            </p>
                        </div>
                    </div>
                </div>

                {/* Procesamiento de Documentos */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-blue-500">description</span>
                            Procesamiento de Documentos
                        </h2>
                    </div>
                    <div className="p-6">
                        <div className="space-y-3">
                            <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                                <span className="material-symbols-outlined text-blue-500 text-[20px]">check_circle</span>
                                <div>
                                    <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
                                        PyMuPDF4LLM (PDF) + MarkItDown (DOCX)
                                    </p>
                                    <p className="text-xs text-blue-600 dark:text-blue-400">
                                        Procesamiento local sin dependencias externas.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Privacy */}
                <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                    <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-indigo-500">shield</span>
                            Privacidad de Datos
                        </h2>
                    </div>
                    <div className="p-6">
                        <label className="flex items-start gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={settings['pii_masking_enabled'] === 'true'}
                                onChange={(e) => setSettings({
                                    ...settings,
                                    pii_masking_enabled: e.target.checked ? 'true' : 'false'
                                })}
                                className="mt-0.5 w-5 h-5 rounded border-slate-300 text-primary focus:ring-primary"
                            />
                            <div>
                                <span className="text-sm text-slate-700 dark:text-slate-300 font-medium">
                                    Enmascarar datos personales (PII)
                                </span>
                                <p className="text-xs text-slate-500 mt-1">
                                    Con Ollama local los datos nunca salen del servidor, por lo que
                                    el enmascaramiento es opcional. Actívalo solo si usas un proveedor en la nube.
                                </p>
                            </div>
                        </label>
                    </div>
                </div>

                {/* Info */}
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-blue-500 text-[20px] mt-0.5">info</span>
                        <div>
                            <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
                                Stack Técnico Actual
                            </p>
                            <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">
                                Ollama (gemma3:4b + nomic-embed-text) · GPU NVIDIA CUDA ·
                                PyMuPDF4LLM · Qdrant · PostgreSQL · Next.js
                            </p>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg text-sm text-rose-700 dark:text-rose-300">
                        {error}
                    </div>
                )}

                <div className="flex items-center gap-3">
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="px-5 py-2 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 transition-colors text-sm disabled:opacity-50"
                    >
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
