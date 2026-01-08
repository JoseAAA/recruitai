"use client";

import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { cn } from "@/lib/utils";
import { jobsApi } from "@/lib/api";

interface ExtractedData {
    title: string;
    requiredSkills: string[];
    preferredSkills: string[];
    minExperienceYears: number;
    educationLevel: string;
    description?: string;
}

interface JobProfilerProps {
    onProfileCreated?: (profile: ExtractedData) => void;
}

export function JobProfiler({ onProfileCreated }: JobProfilerProps) {
    const [jobDescription, setJobDescription] = useState("");
    const [extractedData, setExtractedData] = useState<ExtractedData | null>(null);
    const [isExtracting, setIsExtracting] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [step, setStep] = useState<"input" | "review">("input");
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        accept: {
            "application/pdf": [".pdf"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
            "text/plain": [".txt"],
        },
        maxFiles: 1,
        onDrop: async (files) => {
            if (files.length > 0) {
                // Try to analyze with backend
                try {
                    setIsExtracting(true);
                    const response = await jobsApi.analyze(files[0]);
                    const data = response.data;
                    setExtractedData({
                        title: data.title || "Nuevo Empleo",
                        requiredSkills: data.required_skills || [],
                        preferredSkills: data.preferred_skills || [],
                        minExperienceYears: data.min_experience_years || 0,
                        educationLevel: data.education_level || "bachelor",
                        description: jobDescription,
                    });
                    setStep("review");
                } catch (err) {
                    console.error("Failed to analyze file:", err);
                    setJobDescription(`[Contenido de ${files[0].name}]`);
                } finally {
                    setIsExtracting(false);
                }
            }
        },
    });

    const analyzeDescription = async () => {
        setIsExtracting(true);
        setSaveError(null);

        try {
            // Try backend analysis first
            const response = await jobsApi.analyze(undefined, jobDescription);
            const data = response.data;
            setExtractedData({
                title: data.title || "Nuevo Empleo",
                requiredSkills: data.required_skills || [],
                preferredSkills: data.preferred_skills || [],
                minExperienceYears: data.min_experience_years || 0,
                educationLevel: data.education_level || "bachelor",
                description: jobDescription,
            });
        } catch (err) {
            console.error("Backend analysis failed, using fallback:", err);
            // Fallback: simple extraction
            setExtractedData({
                title: "Nuevo Empleo",
                requiredSkills: extractSkillsFromText(jobDescription),
                preferredSkills: [],
                minExperienceYears: extractYearsFromText(jobDescription),
                educationLevel: "bachelor",
                description: jobDescription,
            });
        }

        setIsExtracting(false);
        setStep("review");
    };

    // Simple skill extraction fallback
    const extractSkillsFromText = (text: string): string[] => {
        const skills = [
            "python", "java", "javascript", "typescript", "react", "angular", "vue",
            "node", "sql", "postgresql", "mysql", "mongodb", "docker", "kubernetes",
            "aws", "azure", "gcp", "linux", "git", "fastapi", "django", "flask",
            "excel", "word", "sap", "scrum", "agile"
        ];
        const found: string[] = [];
        const lower = text.toLowerCase();
        for (const skill of skills) {
            if (lower.includes(skill)) {
                found.push(skill.charAt(0).toUpperCase() + skill.slice(1));
            }
        }
        return found;
    };

    const extractYearsFromText = (text: string): number => {
        const match = text.match(/(\d+)\s*(?:años?|years?)/i);
        return match ? parseInt(match[1]) : 0;
    };

    const removeSkill = (type: "required" | "preferred", skill: string) => {
        if (!extractedData) return;
        if (type === "required") {
            setExtractedData({
                ...extractedData,
                requiredSkills: extractedData.requiredSkills.filter((s) => s !== skill),
            });
        } else {
            setExtractedData({
                ...extractedData,
                preferredSkills: extractedData.preferredSkills.filter((s) => s !== skill),
            });
        }
    };

    const addSkill = (type: "required" | "preferred", skill: string) => {
        if (!extractedData || !skill.trim()) return;
        if (type === "required") {
            setExtractedData({
                ...extractedData,
                requiredSkills: [...extractedData.requiredSkills, skill.trim()],
            });
        } else {
            setExtractedData({
                ...extractedData,
                preferredSkills: [...extractedData.preferredSkills, skill.trim()],
            });
        }
    };

    const saveJobProfile = async () => {
        if (!extractedData) return;

        setIsSaving(true);
        setSaveError(null);

        try {
            await jobsApi.create({
                title: extractedData.title,
                required_skills: extractedData.requiredSkills,
                preferred_skills: extractedData.preferredSkills,
                min_experience_years: extractedData.minExperienceYears,
                education_level: extractedData.educationLevel,
                description: extractedData.description,
                status: "active",
            });

            setSaveSuccess(true);
            onProfileCreated?.(extractedData);

            // Reset after 2 seconds
            setTimeout(() => {
                setStep("input");
                setExtractedData(null);
                setJobDescription("");
                setSaveSuccess(false);
            }, 2000);
        } catch (err: any) {
            console.error("Failed to save job profile:", err);
            setSaveError(err.response?.data?.detail || "Error al guardar el perfil");
        } finally {
            setIsSaving(false);
        }
    };

    const [newRequiredSkill, setNewRequiredSkill] = useState("");
    const [newPreferredSkill, setNewPreferredSkill] = useState("");

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-xl font-semibold text-white">Perfilador de Empleos</h2>
                <p className="text-slate-400 text-sm">
                    Sube o pega una descripción de empleo para extraer requisitos
                </p>
            </div>

            {step === "input" ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Left: Input */}
                    <div className="space-y-4">
                        {/* File Upload */}
                        <div
                            {...getRootProps()}
                            className={cn(
                                "border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all",
                                isDragActive
                                    ? "border-[#135bec] bg-[#135bec]/5"
                                    : "border-[#334155] hover:border-[#135bec]/50"
                            )}
                        >
                            <input {...getInputProps()} />
                            <span className="material-symbols-outlined text-[32px] text-slate-400 mb-2">description</span>
                            <p className="text-sm font-medium text-white">Subir Descripción de Empleo</p>
                            <p className="text-xs text-slate-400">PDF, DOCX o TXT</p>
                        </div>

                        <div className="text-center text-sm text-slate-500">o pega debajo</div>

                        <textarea
                            value={jobDescription}
                            onChange={(e) => setJobDescription(e.target.value)}
                            placeholder="Pega la descripción del empleo aquí..."
                            className="w-full h-64 p-4 rounded-xl bg-[#1e293b] border border-[#334155] focus:border-[#135bec] focus:outline-none focus:ring-1 focus:ring-[#135bec] transition-all resize-none text-white placeholder-slate-500"
                        />

                        <button
                            onClick={analyzeDescription}
                            disabled={!jobDescription.trim() || isExtracting}
                            className="w-full py-3 px-4 rounded-lg bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                        >
                            {isExtracting ? (
                                <>
                                    <span className="material-symbols-outlined animate-spin">progress_activity</span>
                                    Analizando...
                                </>
                            ) : (
                                <>
                                    <span className="material-symbols-outlined">auto_awesome</span>
                                    Extraer Requisitos
                                </>
                            )}
                        </button>
                    </div>

                    {/* Right: Preview Placeholder */}
                    <div className="flex items-center justify-center p-8 rounded-xl border border-dashed border-[#334155] bg-slate-800/30">
                        <p className="text-slate-500 text-center">
                            Las habilidades y requisitos extraídos aparecerán aquí
                        </p>
                    </div>
                </div>
            ) : (
                /* Review Step */
                <div className="space-y-6">
                    {saveSuccess && (
                        <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 flex items-center gap-2">
                            <span className="material-symbols-outlined">check_circle</span>
                            ¡Perfil de empleo creado exitosamente!
                        </div>
                    )}

                    {saveError && (
                        <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-400">
                            {saveError}
                        </div>
                    )}

                    {extractedData && (
                        <>
                            {/* Title */}
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-2">Título del Empleo</label>
                                <input
                                    type="text"
                                    value={extractedData.title}
                                    onChange={(e) => setExtractedData({ ...extractedData, title: e.target.value })}
                                    className="w-full px-4 py-2 rounded-lg bg-[#1e293b] border border-[#334155] focus:border-[#135bec] focus:outline-none text-white"
                                />
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Required Skills */}
                                <div>
                                    <label className="block text-sm font-medium text-rose-400 mb-2">
                                        Habilidades Requeridas
                                    </label>
                                    <div className="flex flex-wrap gap-2 mb-2">
                                        {extractedData.requiredSkills.map((skill) => (
                                            <span
                                                key={skill}
                                                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-rose-500/20 text-rose-400 border border-rose-500/30"
                                            >
                                                {skill}
                                                <button onClick={() => removeSkill("required", skill)} className="hover:text-rose-300">
                                                    <span className="material-symbols-outlined text-[14px]">close</span>
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={newRequiredSkill}
                                            onChange={(e) => setNewRequiredSkill(e.target.value)}
                                            placeholder="Agregar habilidad..."
                                            className="flex-1 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-sm focus:border-[#135bec] focus:outline-none text-white placeholder-slate-500"
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter") {
                                                    addSkill("required", newRequiredSkill);
                                                    setNewRequiredSkill("");
                                                }
                                            }}
                                        />
                                        <button
                                            onClick={() => { addSkill("required", newRequiredSkill); setNewRequiredSkill(""); }}
                                            className="p-1.5 rounded-lg bg-rose-500/20 text-rose-400 hover:bg-rose-500/30"
                                        >
                                            <span className="material-symbols-outlined text-[20px]">add</span>
                                        </button>
                                    </div>
                                </div>

                                {/* Preferred Skills */}
                                <div>
                                    <label className="block text-sm font-medium text-emerald-400 mb-2">
                                        Habilidades Preferidas
                                    </label>
                                    <div className="flex flex-wrap gap-2 mb-2">
                                        {extractedData.preferredSkills.map((skill) => (
                                            <span
                                                key={skill}
                                                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                            >
                                                {skill}
                                                <button onClick={() => removeSkill("preferred", skill)} className="hover:text-emerald-300">
                                                    <span className="material-symbols-outlined text-[14px]">close</span>
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={newPreferredSkill}
                                            onChange={(e) => setNewPreferredSkill(e.target.value)}
                                            placeholder="Agregar habilidad..."
                                            className="flex-1 px-3 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-sm focus:border-[#135bec] focus:outline-none text-white placeholder-slate-500"
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter") {
                                                    addSkill("preferred", newPreferredSkill);
                                                    setNewPreferredSkill("");
                                                }
                                            }}
                                        />
                                        <button
                                            onClick={() => { addSkill("preferred", newPreferredSkill); setNewPreferredSkill(""); }}
                                            className="p-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"
                                        >
                                            <span className="material-symbols-outlined text-[20px]">add</span>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {/* Experience & Education */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">Experiencia Mínima (años)</label>
                                    <input
                                        type="number"
                                        value={extractedData.minExperienceYears}
                                        onChange={(e) => setExtractedData({ ...extractedData, minExperienceYears: parseInt(e.target.value) || 0 })}
                                        className="w-full px-4 py-2 rounded-lg bg-[#1e293b] border border-[#334155] focus:border-[#135bec] focus:outline-none text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-300 mb-2">Nivel Educativo</label>
                                    <select
                                        value={extractedData.educationLevel}
                                        onChange={(e) => setExtractedData({ ...extractedData, educationLevel: e.target.value })}
                                        className="w-full px-4 py-2 rounded-lg bg-[#1e293b] border border-[#334155] focus:border-[#135bec] focus:outline-none text-white"
                                    >
                                        <option value="high_school">Bachillerato</option>
                                        <option value="associate">Técnico</option>
                                        <option value="bachelor">Licenciatura</option>
                                        <option value="master">Maestría</option>
                                        <option value="phd">Doctorado</option>
                                    </select>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-3">
                                <button
                                    onClick={() => { setStep("input"); setExtractedData(null); }}
                                    className="px-4 py-2 rounded-lg border border-[#334155] hover:bg-slate-700 transition-colors text-slate-300"
                                    disabled={isSaving}
                                >
                                    Atrás
                                </button>
                                <button
                                    onClick={saveJobProfile}
                                    disabled={isSaving || saveSuccess}
                                    className="flex-1 py-2 px-4 rounded-lg bg-[#135bec] text-white font-medium hover:bg-[#135bec]/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    {isSaving ? (
                                        <>
                                            <span className="material-symbols-outlined animate-spin">progress_activity</span>
                                            Guardando...
                                        </>
                                    ) : saveSuccess ? (
                                        <>
                                            <span className="material-symbols-outlined">check</span>
                                            ¡Guardado!
                                        </>
                                    ) : (
                                        <>
                                            <span className="material-symbols-outlined">check</span>
                                            Crear Perfil de Empleo
                                        </>
                                    )}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
