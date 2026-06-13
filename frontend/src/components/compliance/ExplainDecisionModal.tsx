"use client";

import { useState, useEffect } from "react";
import { searchApi, CandidateExplanation } from "@/lib/api";

/**
 * Modal "Explicar al candidato" — Reglamento de IA Perú (DS 115-2025-PCM).
 *
 * Cuando un candidato solicita saber por qué fue evaluado de cierta forma,
 * el reclutador abre este modal desde la fila del ranking. Llama al backend,
 * que pide al LLM reformular la evaluación interna en lenguaje accesible.
 * El reclutador puede copiar el texto al portapapeles para responderle
 * al candidato vía email, WhatsApp o el canal que use la empresa.
 *
 * El backend audita cada generación para demostrar a la ANPD que el derecho
 * a explicación se atendió.
 */

interface Props {
    candidateId: string;
    jobId: string;
    candidateName: string;
    onClose: () => void;
}

export function ExplainDecisionModal({
    candidateId,
    jobId,
    candidateName,
    onClose,
}: Props) {
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [data, setData] = useState<CandidateExplanation | null>(null);
    const [copied, setCopied] = useState(false);

    // Disparar generación al montar. La explicación puede tardar 15-40s
    // porque pasa por el LLM; el spinner del cuerpo es el feedback al usuario.
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await searchApi.explainToCandidate(candidateId, jobId);
                if (!cancelled) {
                    setData(res.data);
                    setLoading(false);
                }
            } catch (err: any) {
                if (!cancelled) {
                    setError(
                        err?.response?.data?.detail ||
                            "No pudimos generar la explicación. Asegúrate de haber ejecutado el matching IA antes."
                    );
                    setLoading(false);
                }
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [candidateId, jobId]);

    const handleCopy = async () => {
        if (!data?.explanation_for_candidate) return;
        try {
            await navigator.clipboard.writeText(data.explanation_for_candidate);
            setCopied(true);
            setTimeout(() => setCopied(false), 2500);
        } catch {
            // Fallback silencioso: el usuario puede seleccionar y copiar a mano.
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm p-4"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
        >
            <div
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-start gap-3 p-5 border-b border-slate-200 dark:border-slate-700">
                    <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                        <span className="material-symbols-outlined text-[22px]">forum</span>
                    </div>
                    <div className="flex-1 min-w-0">
                        <h2 className="text-base font-bold text-slate-900 dark:text-white">
                            Explicación para {candidateName}
                        </h2>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            Texto generado para responderle si pregunta por su evaluación.
                            La decisión final es tuya.
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors p-1 rounded"
                        aria-label="Cerrar"
                    >
                        <span className="material-symbols-outlined text-[20px]">close</span>
                    </button>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto p-5">
                    {loading && (
                        <div className="flex flex-col items-center justify-center py-12 gap-3">
                            <span className="material-symbols-outlined text-[36px] text-blue-500 animate-spin">
                                sync
                            </span>
                            <p className="text-sm text-slate-500">
                                Redactando explicación en lenguaje accesible…
                            </p>
                        </div>
                    )}

                    {error && (
                        <div className="flex items-start gap-3 p-4 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-rose-700 dark:text-rose-300">
                            <span className="material-symbols-outlined text-[20px] flex-shrink-0 mt-0.5">
                                error
                            </span>
                            <p className="text-sm">{error}</p>
                        </div>
                    )}

                    {data && !error && (
                        <>
                            <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4">
                                <p className="text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
                                    {data.explanation_for_candidate}
                                </p>
                            </div>
                            <p className="text-[11px] text-slate-400 mt-3 flex items-start gap-1.5 leading-relaxed">
                                <span className="material-symbols-outlined text-[14px] mt-0.5">
                                    shield_lock
                                </span>
                                Este texto se generó automáticamente como ayuda. Revísalo y
                                ajústalo antes de enviarlo. Cumple el derecho a explicación
                                del Reglamento de IA Perú (DS 115-2025-PCM).
                            </p>
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between gap-3 p-5 border-t border-slate-200 dark:border-slate-700">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                    >
                        Cerrar
                    </button>
                    <button
                        onClick={handleCopy}
                        disabled={!data || loading}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-primary hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">
                            {copied ? "check" : "content_copy"}
                        </span>
                        {copied ? "Copiado" : "Copiar texto"}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ExplainDecisionModal;
