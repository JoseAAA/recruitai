"use client";

import { useState } from "react";
import { candidatesApi, CandidateDetail } from "@/lib/api";

type ExperienceEntry = NonNullable<CandidateDetail["experience"]>[number];

interface DraftEntry {
    title: string;
    company: string;
    start_date: string;   // "YYYY-MM" or ""
    end_date: string;     // "YYYY-MM" or ""
    is_current: boolean;
    description: string;
}

function toDraft(e: ExperienceEntry): DraftEntry {
    const cut = (d?: string | null) => (d ? d.slice(0, 7) : "");
    return {
        title: e.title || "",
        company: e.company || "",
        start_date: cut(e.start_date),
        end_date: e.is_current ? "" : cut(e.end_date),
        is_current: !!e.is_current,
        description: e.description || "",
    };
}

interface Props {
    candidateId: string;
    initial: ExperienceEntry[];
    onClose: () => void;
    onSaved: (updated: CandidateDetail) => void;
}

const ExperienceEditor: React.FC<Props> = ({ candidateId, initial, onClose, onSaved }) => {
    const [drafts, setDrafts] = useState<DraftEntry[]>(
        initial.length > 0
            ? initial.map(toDraft)
            : [{ title: "", company: "", start_date: "", end_date: "", is_current: false, description: "" }],
    );
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const update = (idx: number, patch: Partial<DraftEntry>) => {
        setDrafts(prev => prev.map((d, i) => (i === idx ? { ...d, ...patch } : d)));
    };

    const remove = (idx: number) => {
        setDrafts(prev => (prev.length === 1 ? prev : prev.filter((_, i) => i !== idx)));
    };

    const add = () => {
        setDrafts(prev => [
            ...prev,
            { title: "", company: "", start_date: "", end_date: "", is_current: false, description: "" },
        ]);
    };

    const handleSave = async () => {
        setError(null);

        // Drop blank rows so the user can leave half-typed entries behind without saving them.
        const payload = drafts
            .filter(d => d.title.trim() || d.company.trim())
            .map(d => ({
                title: d.title.trim() || null,
                company: d.company.trim() || null,
                start_date: d.start_date || null,
                end_date: d.is_current ? null : (d.end_date || null),
                is_current: d.is_current,
                description: d.description.trim() || null,
            }));

        for (let i = 0; i < payload.length; i++) {
            const e = payload[i];
            if (e.start_date && e.end_date && e.end_date < e.start_date) {
                setError(`Entrada ${i + 1}: la fecha fin debe ser posterior a la de inicio`);
                return;
            }
        }

        setSaving(true);
        try {
            const res = await candidatesApi.updateExperience(candidateId, payload);
            onSaved(res.data);
            onClose();
        } catch (err: any) {
            setError(err.response?.data?.detail || "No se pudo guardar la experiencia");
        } finally {
            setSaving(false);
        }
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4"
            onClick={onClose}
        >
            <div
                className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-slate-200 dark:border-slate-700"
                onClick={e => e.stopPropagation()}
            >
                <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <span className="material-symbols-outlined text-emerald-500">work_history</span>
                            Editar experiencia laboral
                        </h2>
                        <p className="text-xs text-slate-500 mt-0.5">
                            Los años totales se recalculan automáticamente al guardar.
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                        <span className="material-symbols-outlined">close</span>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                    {drafts.map((d, idx) => (
                        <div
                            key={idx}
                            className="p-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/40 dark:bg-slate-800/40 space-y-3"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                    Posición {idx + 1}
                                </span>
                                {drafts.length > 1 && (
                                    <button
                                        onClick={() => remove(idx)}
                                        className="text-xs text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-900/20 px-2 py-1 rounded flex items-center gap-1"
                                    >
                                        <span className="material-symbols-outlined text-[14px]">delete</span>
                                        Quitar
                                    </button>
                                )}
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs text-slate-500 mb-1">Cargo</label>
                                    <input
                                        type="text"
                                        value={d.title}
                                        onChange={e => update(idx, { title: e.target.value })}
                                        placeholder="ej. Abogada Penalista"
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-500 mb-1">Empresa</label>
                                    <input
                                        type="text"
                                        value={d.company}
                                        onChange={e => update(idx, { company: e.target.value })}
                                        placeholder="ej. Estudio Jurídico Ensigna"
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-500 mb-1">Fecha inicio</label>
                                    <input
                                        type="month"
                                        value={d.start_date}
                                        onChange={e => update(idx, { start_date: e.target.value })}
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs text-slate-500 mb-1">
                                        Fecha fin {d.is_current && <span className="text-emerald-500">(actual)</span>}
                                    </label>
                                    <input
                                        type="month"
                                        value={d.end_date}
                                        onChange={e => update(idx, { end_date: e.target.value })}
                                        disabled={d.is_current}
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none disabled:opacity-50 disabled:cursor-not-allowed"
                                    />
                                </div>
                            </div>

                            <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={d.is_current}
                                    onChange={e =>
                                        update(idx, {
                                            is_current: e.target.checked,
                                            end_date: e.target.checked ? "" : d.end_date,
                                        })
                                    }
                                    className="w-4 h-4 rounded border-slate-300 text-primary focus:ring-primary"
                                />
                                Trabajo actual
                            </label>

                            <div>
                                <label className="block text-xs text-slate-500 mb-1">
                                    Descripción / logros (opcional)
                                </label>
                                <textarea
                                    value={d.description}
                                    onChange={e => update(idx, { description: e.target.value })}
                                    rows={3}
                                    placeholder="Una línea por logro o responsabilidad principal"
                                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-primary outline-none resize-y"
                                />
                            </div>
                        </div>
                    ))}

                    <button
                        onClick={add}
                        className="w-full py-2.5 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 text-slate-500 hover:border-primary hover:text-primary text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                    >
                        <span className="material-symbols-outlined text-[18px]">add</span>
                        Agregar otra posición
                    </button>
                </div>

                {error && (
                    <div className="px-6 py-2 bg-rose-50 dark:bg-rose-900/20 border-t border-rose-200 dark:border-rose-800 text-sm text-rose-700 dark:text-rose-300 flex items-center gap-2">
                        <span className="material-symbols-outlined text-[16px]">error</span>
                        {error}
                    </div>
                )}

                <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex items-center justify-end gap-2 bg-slate-50/50 dark:bg-slate-800/30">
                    <button
                        onClick={onClose}
                        disabled={saving}
                        className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg disabled:opacity-50"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="px-5 py-2 bg-primary text-white text-sm font-semibold rounded-lg hover:bg-blue-600 disabled:opacity-50 flex items-center gap-2"
                    >
                        {saving && (
                            <span className="material-symbols-outlined text-[16px] animate-spin">
                                progress_activity
                            </span>
                        )}
                        {saving ? "Guardando..." : "Guardar cambios"}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ExperienceEditor;
