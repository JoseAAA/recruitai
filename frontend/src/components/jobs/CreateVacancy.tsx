"use client";

import React, { useState, useRef, KeyboardEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jobsApi, ScoringDimension, LanguageRequirement } from "@/lib/api";

const DEFAULT_SCORING: ScoringDimension[] = [
    { dimension: "skills", weight: 0.40, description: "Skills técnicos y blandos" },
    { dimension: "experience", weight: 0.35, description: "Experiencia laboral relevante" },
    { dimension: "education", weight: 0.25, description: "Formación académica" },
];

const SCORING_PRESETS = [
    {
        label: "Técnico",
        sublabel: "50/30/20",
        config: [
            { dimension: "skills", weight: 0.50, description: "Skills técnicos y blandos" },
            { dimension: "experience", weight: 0.30, description: "Experiencia laboral relevante" },
            { dimension: "education", weight: 0.20, description: "Formación académica" },
        ],
    },
    {
        label: "Liderazgo",
        sublabel: "35/35/30",
        config: [
            { dimension: "skills", weight: 0.35, description: "Skills técnicos y blandos" },
            { dimension: "experience", weight: 0.35, description: "Experiencia laboral relevante" },
            { dimension: "education", weight: 0.30, description: "Formación académica" },
        ],
    },
    {
        label: "Académico",
        sublabel: "35/30/35",
        config: [
            { dimension: "skills", weight: 0.35, description: "Skills técnicos y blandos" },
            { dimension: "experience", weight: 0.30, description: "Experiencia laboral relevante" },
            { dimension: "education", weight: 0.35, description: "Formación académica" },
        ],
    },
];

const SENIORITY_OPTIONS = [
    { value: "", label: "Seleccionar..." },
    { value: "intern", label: "Pasante / Trainee" },
    { value: "junior", label: "Junior (0-2 años)" },
    { value: "mid-level", label: "Semi-Senior (2-4 años)" },
    { value: "senior", label: "Senior (4+ años)" },
    { value: "lead", label: "Lead / Especialista" },
    { value: "manager", label: "Manager / Jefe" },
    { value: "director", label: "Director / Head" },
];

const EDUCATION_OPTIONS = [
    { value: "", label: "Sin requisito" },
    { value: "high_school", label: "Secundaria / Bachillerato" },
    { value: "associate", label: "Técnico Superior" },
    { value: "bachelor", label: "Universitaria (Bachiller / Licenciatura)" },
    { value: "master", label: "Posgrado (Maestría / MBA)" },
    { value: "phd", label: "Doctorado" },
];

const LANGUAGE_LEVEL_OPTIONS = ["Básico", "Intermedio", "Avanzado", "Nativo", "Bilingüe"];

// ── Skill chip input ──────────────────────────────────────────────────────────
interface SkillChipsProps {
    label: string;
    color: "indigo" | "emerald";
    skills: string[];
    onAdd: (skill: string) => void;
    onRemove: (idx: number) => void;
}

function SkillChips({ label, color, skills, onAdd, onRemove }: SkillChipsProps) {
    const [inputVal, setInputVal] = useState("");

    const commit = () => {
        const vals = inputVal.split(",").map(s => s.trim()).filter(s => s.length > 0);
        vals.forEach(v => onAdd(v));
        setInputVal("");
    };

    const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
        } else if (e.key === "Backspace" && inputVal === "" && skills.length > 0) {
            onRemove(skills.length - 1);
        }
    };

    const chipColor =
        color === "indigo"
            ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300"
            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300";

    return (
        <div className="space-y-1.5">
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                {label}
            </label>
            <div className="min-h-[44px] flex flex-wrap gap-1.5 px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-primary transition-shadow">
                {skills.map((s, i) => (
                    <span
                        key={i}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${chipColor}`}
                    >
                        {s}
                        <button
                            type="button"
                            onClick={() => onRemove(i)}
                            className="hover:opacity-70 ml-0.5"
                        >
                            ×
                        </button>
                    </span>
                ))}
                <input
                    className="flex-1 min-w-[120px] bg-transparent outline-none text-sm text-slate-900 dark:text-white placeholder-slate-400"
                    placeholder={skills.length === 0 ? "Escribe y presiona Enter o coma..." : "Agregar más..."}
                    value={inputVal}
                    onChange={e => setInputVal(e.target.value)}
                    onKeyDown={handleKey}
                    onBlur={commit}
                />
            </div>
            <p className="text-[10px] text-slate-400">
                Presiona <kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-800 rounded text-[10px]">Enter</kbd> o coma para agregar. Backspace elimina el último.
            </p>
        </div>
    );
}

// ── Main component ────────────────────────────────────────────────────────────
const CreateVacancy: React.FC = () => {
    const router = useRouter();

    // ── form state ───────────────────────────────────────────────────────────
    const [jobTitle, setJobTitle] = useState("");
    const [department, setDepartment] = useState("");
    const [seniority, setSeniority] = useState("");
    // Modalidad sin default: el reclutador la elige cuando el documento no la
    // declara explícitamente. Antes el default "hybrid" generaba falsos
    // positivos para vacantes de RRHH formales que omiten la modalidad.
    const [modality, setModality] = useState("");
    const [industry, setIndustry] = useState("");
    const [location, setLocation] = useState("");
    const [minExperience, setMinExperience] = useState(0);
    const [educationLevel, setEducationLevel] = useState("");
    const [description, setDescription] = useState("");
    const [responsibilities, setResponsibilities] = useState<string[]>(["", ""]);
    const [keyObjectives, setKeyObjectives] = useState<string[]>(["", ""]);
    const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
    const [preferredSkills, setPreferredSkills] = useState<string[]>([]);
    const [requiredLanguages, setRequiredLanguages] = useState<LanguageRequirement[]>([]);
    const [scoringConfig, setScoringConfig] = useState<ScoringDimension[]>(DEFAULT_SCORING);

    // ── status ───────────────────────────────────────────────────────────────
    const [isSaving, setIsSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [analyzeError, setAnalyzeError] = useState<string | null>(null);
    const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
    const [jdWarnings, setJdWarnings] = useState<string[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ── scoring ──────────────────────────────────────────────────────────────
    const scoringTotal = scoringConfig.reduce((sum, d) => sum + d.weight, 0);
    const scoringValid = Math.abs(scoringTotal - 1.0) < 0.01;

    const updateScoringWeight = (idx: number, value: number) => {
        setScoringConfig(scoringConfig.map((d, i) => i === idx ? { ...d, weight: value } : d));
    };

    // ── responsibilities & objectives helpers ─────────────────────────────────
    const addItem = (setter: React.Dispatch<React.SetStateAction<string[]>>, list: string[]) =>
        setter([...list, ""]);
    const updateItem = (setter: React.Dispatch<React.SetStateAction<string[]>>, list: string[], idx: number, val: string) => {
        const n = [...list]; n[idx] = val; setter(n);
    };
    const removeItem = (setter: React.Dispatch<React.SetStateAction<string[]>>, list: string[], idx: number) =>
        setter(list.filter((_, i) => i !== idx));

    // ── skills helpers ────────────────────────────────────────────────────────
    const addSkill = (type: "required" | "preferred", skill: string) => {
        if (!skill) return;
        if (type === "required") setRequiredSkills(prev => prev.includes(skill) ? prev : [...prev, skill]);
        else setPreferredSkills(prev => prev.includes(skill) ? prev : [...prev, skill]);
    };
    const removeSkill = (type: "required" | "preferred", idx: number) => {
        if (type === "required") setRequiredSkills(prev => prev.filter((_, i) => i !== idx));
        else setPreferredSkills(prev => prev.filter((_, i) => i !== idx));
    };

    // ── file upload / LLM analyze ─────────────────────────────────────────────
    const handleFileUpload = async (file: File) => {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (![".pdf", ".docx"].includes(ext)) {
            setAnalyzeError("Solo se aceptan archivos PDF o DOCX");
            return;
        }
        setIsAnalyzing(true);
        setAnalyzeError(null);
        setUploadedFileName(file.name);
        try {
            const res = await jobsApi.analyze(file);
            const data = res.data as any;
            if (data.title) setJobTitle(data.title);
            if (data.department) setDepartment(data.department);
            if (data.seniority_level) setSeniority(data.seniority_level);
            if (data.work_modality) setModality(data.work_modality);
            if (data.industry) setIndustry(data.industry);
            if (data.location) setLocation(data.location);
            if (data.description) setDescription(data.description);
            if (data.min_experience_years) setMinExperience(data.min_experience_years);
            if (data.education_level) setEducationLevel(data.education_level);
            if (data.required_skills?.length) setRequiredSkills(data.required_skills);
            if (data.preferred_skills?.length) setPreferredSkills(data.preferred_skills);
            if (data.responsibilities?.length) setResponsibilities(data.responsibilities.slice(0, 8));
            if (data.key_objectives?.length) setKeyObjectives(data.key_objectives.slice(0, 6));
            if (data.required_languages?.length) setRequiredLanguages(data.required_languages);

            // JD quality warnings
            const warnings: string[] = [];
            const skills = data.required_skills ?? [];
            if (skills.length < 3) warnings.push("Se extrajeron menos de 3 habilidades requeridas — el matching será poco preciso. Agrégalas manualmente.");
            if ((data.min_experience_years ?? 0) > 8) warnings.push("El requisito de experiencia supera los 8 años — podría limitar demasiado el pool de candidatos.");
            if (!data.description || String(data.description).trim().length < 50) warnings.push("La descripción del puesto es muy corta — una descripción rica mejora el matching semántico.");
            if (!data.required_languages?.length) warnings.push("No se detectaron requisitos de idioma — si el inglés u otro idioma es relevante, agrégalo.");
            setJdWarnings(warnings);
        } catch (err: any) {
            // Un timeout/corte de conexión no trae response.data.detail. Con
            // Ollama local el análisis puede tomar ~40 s: es lentitud, no un
            // error real. Mensaje honesto en vez de "Error al analizar".
            const timedOut = err.code === "ECONNABORTED" || !err.response;
            setAnalyzeError(
                err.response?.data?.detail ||
                (timedOut
                    ? "El análisis está tardando más de lo normal (con el modelo local puede tomar ~40 s). Espera unos segundos y vuelve a intentar."
                    : "Error al analizar el documento"),
            );
            setUploadedFileName(null);
        } finally {
            setIsAnalyzing(false);
        }
    };

    // ── save ──────────────────────────────────────────────────────────────────
    const handleSaveJob = async () => {
        if (!jobTitle.trim()) { setSaveError("El título del puesto es requerido"); return; }
        if (requiredSkills.length === 0) { setSaveError("Agrega al menos una habilidad requerida para mejorar el matching"); return; }

        setIsSaving(true);
        setSaveError(null);
        try {
            await jobsApi.create({
                title: jobTitle,
                department: department || undefined,
                description: description || undefined,
                seniority_level: seniority || undefined,
                work_modality: modality || undefined,
                industry: industry || undefined,
                location: location || undefined,
                required_skills: requiredSkills,
                preferred_skills: preferredSkills,
                responsibilities: responsibilities.filter(r => r.trim()),
                key_objectives: keyObjectives.filter(k => k.trim()),
                min_experience_years: minExperience,
                education_level: educationLevel || undefined,
                status: "active",
                required_languages: requiredLanguages.filter(l => l.idioma.trim()),
                scoring_config: scoringValid ? scoringConfig : undefined,
            });
            router.push("/jobs");
        } catch (err: any) {
            setSaveError(err.response?.data?.detail || "Error al guardar la vacante");
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <>
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <nav className="flex text-sm text-slate-500 mb-1">
                        <Link href="/jobs" className="hover:text-slate-900 dark:hover:text-slate-300 transition-colors">
                            Empleos
                        </Link>
                        <span className="mx-2">/</span>
                        <span className="text-slate-900 dark:text-white font-medium">Nueva Vacante</span>
                    </nav>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Creación de Vacante</h1>
                </div>
                <div className="flex gap-3 items-center">
                    {saveError && <span className="text-sm text-rose-500">{saveError}</span>}
                    <button
                        onClick={handleSaveJob}
                        disabled={isSaving || !jobTitle.trim()}
                        className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm disabled:opacity-50"
                    >
                        {isSaving ? "Guardando..." : "Guardar Borrador"}
                    </button>
                    <button
                        onClick={handleSaveJob}
                        disabled={isSaving || !jobTitle.trim()}
                        className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors shadow-sm flex items-center gap-2 disabled:opacity-50"
                    >
                        <span>{isSaving ? "Publicando..." : "Publicar Vacante"}</span>
                        <span className="material-symbols-outlined text-[18px]">send</span>
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left Column: sidebar */}
                <div className="lg:col-span-4 flex flex-col gap-6">

                    {/* File Upload */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
                                <span className="p-1 rounded bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400">
                                    <span className="material-symbols-outlined text-[18px]">upload_file</span>
                                </span>
                                Cargar Documento
                            </h3>
                        </div>
                        <div className="p-5">
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf,.docx"
                                className="hidden"
                                onChange={e => {
                                    const f = e.target.files?.[0];
                                    if (f) handleFileUpload(f);
                                    e.target.value = "";
                                }}
                            />
                            <div
                                className={`border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center transition-all cursor-pointer
                                    ${isAnalyzing
                                        ? "border-primary/40 bg-primary/5"
                                        : uploadedFileName
                                            ? "border-emerald-400/60 bg-emerald-50 dark:bg-emerald-500/10"
                                            : "border-slate-300 dark:border-slate-700 hover:border-primary/50 bg-slate-50 dark:bg-slate-800/30 hover:bg-slate-100 dark:hover:bg-slate-800/80"
                                    }`}
                                onClick={() => !isAnalyzing && fileInputRef.current?.click()}
                                onDragOver={e => e.preventDefault()}
                                onDrop={e => {
                                    e.preventDefault();
                                    const f = e.dataTransfer.files?.[0];
                                    if (f && !isAnalyzing) handleFileUpload(f);
                                }}
                            >
                                {isAnalyzing ? (
                                    <>
                                        <span className="material-symbols-outlined text-[32px] text-primary animate-spin mb-2">sync</span>
                                        <p className="text-sm font-medium text-primary">Analizando documento...</p>
                                        <p className="text-xs text-slate-400 mt-1">El LLM extrae los requisitos del puesto</p>
                                    </>
                                ) : uploadedFileName ? (
                                    <>
                                        <span className="material-symbols-outlined text-[32px] text-emerald-500 mb-2">check_circle</span>
                                        <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400 truncate max-w-full px-2">{uploadedFileName}</p>
                                        <p className="text-xs text-slate-400 mt-1">Datos extraídos · Haz clic para cambiar</p>
                                    </>
                                ) : (
                                    <>
                                        <span className="material-symbols-outlined text-[32px] text-slate-400 mb-2">cloud_upload</span>
                                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Arrastra tu PDF o DOCX</p>
                                        <p className="text-xs text-slate-400 mt-1">El LLM extraerá todos los campos · Máx 10MB</p>
                                    </>
                                )}
                            </div>
                            {analyzeError && <p className="mt-2 text-xs text-rose-500">{analyzeError}</p>}
                            {jdWarnings.length > 0 && (
                                <div className="mt-3 rounded-lg border border-amber-300/40 bg-amber-50 dark:bg-amber-500/10 p-3 space-y-1.5">
                                    <p className="text-xs font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                                        <span className="material-symbols-outlined text-[14px]">warning</span>
                                        Sugerencias de calidad
                                    </p>
                                    {jdWarnings.map((w, i) => (
                                        <p key={i} className="text-xs text-amber-700 dark:text-amber-300 pl-1">· {w}</p>
                                    ))}
                                    <button
                                        type="button"
                                        onClick={() => setJdWarnings([])}
                                        className="text-[10px] text-amber-500 hover:text-amber-400 mt-1"
                                    >
                                        Descartar
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Scoring Weights */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
                                <span className="p-1 rounded bg-violet-100 text-violet-600 dark:bg-violet-500/20 dark:text-violet-400">
                                    <span className="material-symbols-outlined text-[18px]">equalizer</span>
                                </span>
                                Pesos de Scoring
                            </h3>
                            <button
                                type="button"
                                onClick={() => setScoringConfig([...DEFAULT_SCORING])}
                                className="text-xs text-indigo-500 hover:text-indigo-400"
                            >
                                Restaurar
                            </button>
                        </div>
                        <div className="p-5 space-y-3">
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                                Define el peso de cada dimensión en el matching para este puesto.
                            </p>
                            {/* Preset buttons */}
                            <div className="flex gap-1.5 flex-wrap">
                                {SCORING_PRESETS.map(preset => (
                                    <button
                                        key={preset.label}
                                        type="button"
                                        onClick={() => setScoringConfig([...preset.config])}
                                        className="flex flex-col items-center px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all text-slate-600 dark:text-slate-400"
                                    >
                                        <span className="text-xs font-semibold leading-none">{preset.label}</span>
                                        <span className="text-[10px] text-slate-400 mt-0.5">{preset.sublabel}</span>
                                    </button>
                                ))}
                            </div>
                            {scoringConfig.map((dim, idx) => (
                                <div key={dim.dimension} className="flex items-center gap-3">
                                    <span className="w-24 text-sm font-medium text-slate-700 dark:text-slate-300 capitalize">
                                        {dim.dimension === "skills" ? "Skills" : dim.dimension === "experience" ? "Experiencia" : "Educación"}
                                    </span>
                                    <input
                                        type="range"
                                        min={0} max={1} step={0.05}
                                        value={dim.weight}
                                        onChange={e => updateScoringWeight(idx, parseFloat(e.target.value))}
                                        className="flex-1 accent-indigo-500"
                                    />
                                    <span className={`w-12 text-right text-sm font-bold ${scoringValid ? "text-slate-700 dark:text-slate-300" : "text-rose-400"}`}>
                                        {Math.round(dim.weight * 100)}%
                                    </span>
                                </div>
                            ))}
                            {!scoringValid && (
                                <p className="text-xs text-rose-400">Los pesos deben sumar 100%. Actualmente: {Math.round(scoringTotal * 100)}%</p>
                            )}
                            {scoringValid && (
                                <p className="text-xs text-emerald-500">✓ Pesos correctos (100%)</p>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Column: Form */}
                <div className="lg:col-span-8 space-y-6">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/50 rounded-t-xl">
                            <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-slate-400">edit_note</span>
                                <h2 className="text-lg font-bold text-slate-900 dark:text-white">Perfil del Puesto</h2>
                            </div>
                            <span className="text-xs font-medium px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
                                Edición Manual
                            </span>
                        </div>

                        <div className="p-6 space-y-6">
                            {/* ── Datos generales ─────────────────────────────────── */}
                            <div>
                                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[14px]">info</span>
                                    Datos Generales
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                                    {/* Título */}
                                    <div className="md:col-span-2 space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Título del Puesto <span className="text-rose-500">*</span>
                                        </label>
                                        <input
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            placeholder="Ej: Científico de Datos Senior"
                                            value={jobTitle}
                                            onChange={e => setJobTitle(e.target.value)}
                                        />
                                    </div>

                                    {/* Departamento */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Departamento / Área
                                        </label>
                                        <input
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            placeholder="Ej: Tecnología, Legal, Comercial..."
                                            value={department}
                                            onChange={e => setDepartment(e.target.value)}
                                        />
                                        <p className="text-[10px] text-slate-400">Solo organizativo — no afecta el matching.</p>
                                    </div>

                                    {/* Seniority */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Nivel Jerárquico
                                        </label>
                                        <select
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            value={seniority}
                                            onChange={e => setSeniority(e.target.value)}
                                        >
                                            {SENIORITY_OPTIONS.map(o => (
                                                <option key={o.value} value={o.value}>{o.label}</option>
                                            ))}
                                        </select>
                                    </div>

                                    {/* Modalidad */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Modalidad
                                        </label>
                                        <select
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            value={modality}
                                            onChange={e => setModality(e.target.value)}
                                        >
                                            <option value="">Sin especificar</option>
                                            <option value="onsite">Presencial</option>
                                            <option value="remote">Remoto</option>
                                            <option value="hybrid">Híbrido</option>
                                        </select>
                                    </div>

                                    {/* Industria */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Industria / Sector
                                        </label>
                                        <input
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            placeholder="Ej: Fintech, Retail, Salud, Tecnología..."
                                            value={industry}
                                            onChange={e => setIndustry(e.target.value)}
                                        />
                                    </div>

                                    {/* Lugar de trabajo / Ubicación */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Lugar de Trabajo
                                        </label>
                                        <input
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            placeholder="Ej: Lima — San Isidro, Chinchón, Trujillo..."
                                            value={location}
                                            onChange={e => setLocation(e.target.value)}
                                        />
                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                            Ciudad, distrito o sede declarada en el documento. Útil para filtrar candidatos por geografía.
                                        </p>
                                    </div>

                                    {/* Años experiencia */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Experiencia Mínima (años)
                                        </label>
                                        <input
                                            type="number"
                                            min={0}
                                            max={30}
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            value={minExperience}
                                            onChange={e => setMinExperience(parseInt(e.target.value) || 0)}
                                        />
                                    </div>

                                    {/* Educación */}
                                    <div className="space-y-1.5">
                                        <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                            Formación Académica Requerida
                                        </label>
                                        <select
                                            className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            value={educationLevel}
                                            onChange={e => setEducationLevel(e.target.value)}
                                        >
                                            {EDUCATION_OPTIONS.map(o => (
                                                <option key={o.value} value={o.value}>{o.label}</option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            {/* ── Descripción ──────────────────────────────────────── */}
                            <div className="space-y-2">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                    Objetivo / Descripción del Puesto
                                </label>
                                <textarea
                                    className="w-full px-4 py-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent resize-y h-28 outline-none shadow-sm"
                                    placeholder="Describe el objetivo del rol, contexto del equipo y lo que se espera del candidato..."
                                    value={description}
                                    onChange={e => setDescription(e.target.value)}
                                />
                                <p className="text-xs text-slate-400">Una descripción rica mejora significativamente la calidad del matching semántico.</p>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            {/* ── Habilidades requeridas ────────────────────────────── */}
                            <div>
                                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[14px]">psychology</span>
                                    Habilidades
                                    <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400 font-bold">
                                        Impacto directo en scoring
                                    </span>
                                </h3>
                                <div className="space-y-5">
                                    <SkillChips
                                        label="Habilidades Técnicas Requeridas *"
                                        color="indigo"
                                        skills={requiredSkills}
                                        onAdd={s => addSkill("required", s)}
                                        onRemove={i => removeSkill("required", i)}
                                    />
                                    <SkillChips
                                        label="Habilidades Deseables (no obligatorias)"
                                        color="emerald"
                                        skills={preferredSkills}
                                        onAdd={s => addSkill("preferred", s)}
                                        onRemove={i => removeSkill("preferred", i)}
                                    />
                                </div>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            {/* ── Idiomas Requeridos ───────────────────────────────── */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[14px]">translate</span>
                                    Idiomas Requeridos
                                    <span className="ml-1 px-1.5 py-0.5 text-[10px] rounded bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400 font-bold">
                                        Afecta el matching
                                    </span>
                                </h3>
                                <p className="text-xs text-slate-400">Agrega los idiomas que el candidato debe dominar. Se considerarán en el scoring semántico.</p>
                                <div className="space-y-2">
                                    {requiredLanguages.map((lang, idx) => (
                                        <div key={idx} className="flex items-center gap-2">
                                            <input
                                                className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                                                placeholder="Ej: Inglés, Portugués..."
                                                value={lang.idioma}
                                                onChange={e => {
                                                    const n = [...requiredLanguages];
                                                    n[idx] = { ...n[idx], idioma: e.target.value };
                                                    setRequiredLanguages(n);
                                                }}
                                            />
                                            <select
                                                className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                                                value={lang.nivel}
                                                onChange={e => {
                                                    const n = [...requiredLanguages];
                                                    n[idx] = { ...n[idx], nivel: e.target.value };
                                                    setRequiredLanguages(n);
                                                }}
                                            >
                                                {LANGUAGE_LEVEL_OPTIONS.map(l => (
                                                    <option key={l} value={l}>{l}</option>
                                                ))}
                                            </select>
                                            <label className="flex items-center gap-1.5 text-xs text-slate-500 whitespace-nowrap cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={lang.obligatorio}
                                                    onChange={e => {
                                                        const n = [...requiredLanguages];
                                                        n[idx] = { ...n[idx], obligatorio: e.target.checked };
                                                        setRequiredLanguages(n);
                                                    }}
                                                    className="rounded"
                                                />
                                                Obligatorio
                                            </label>
                                            <button
                                                onClick={() => setRequiredLanguages(requiredLanguages.filter((_, i) => i !== idx))}
                                                className="text-slate-300 hover:text-rose-500"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">delete</span>
                                            </button>
                                        </div>
                                    ))}
                                    <button
                                        onClick={() => setRequiredLanguages([...requiredLanguages, { idioma: "", nivel: "Intermedio", obligatorio: true }])}
                                        className="flex items-center gap-2 text-sm text-primary font-medium hover:text-primary/80 transition-colors px-1 mt-1"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">add_circle</span>
                                        Agregar idioma
                                    </button>
                                </div>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            {/* ── Responsabilidades ─────────────────────────────────── */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[14px]">task_alt</span>
                                    Responsabilidades Principales
                                </h3>
                                <div className="space-y-2">
                                    {responsibilities.map((resp, idx) => (
                                        <div key={idx} className="flex items-center gap-2 group">
                                            <span className="material-symbols-outlined text-slate-300 text-[18px]">drag_indicator</span>
                                            <input
                                                className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                                                placeholder="Ej: Diseñar y entrenar modelos de ML para predicción..."
                                                value={resp}
                                                onChange={e => updateItem(setResponsibilities, responsibilities, idx, e.target.value)}
                                            />
                                            <button onClick={() => removeItem(setResponsibilities, responsibilities, idx)} className="text-slate-300 hover:text-rose-500">
                                                <span className="material-symbols-outlined text-[20px]">delete</span>
                                            </button>
                                        </div>
                                    ))}
                                    <button
                                        onClick={() => addItem(setResponsibilities, responsibilities)}
                                        className="flex items-center gap-2 text-sm text-primary font-medium hover:text-primary/80 transition-colors px-1 mt-1"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">add_circle</span>
                                        Agregar responsabilidad
                                    </button>
                                </div>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            {/* ── Objetivos Clave / KPIs ────────────────────────────── */}
                            <div className="space-y-3">
                                <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                    <span className="material-symbols-outlined text-[14px]">flag</span>
                                    Objetivos Clave / KPIs
                                </h3>
                                <p className="text-xs text-slate-400">Resultados esperados en los primeros 6-12 meses. Mejoran el matching de experiencia.</p>
                                <div className="space-y-2">
                                    {keyObjectives.map((obj, idx) => (
                                        <div key={idx} className="flex items-center gap-2 group">
                                            <span className="material-symbols-outlined text-slate-300 text-[18px]">drag_indicator</span>
                                            <input
                                                className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                                                placeholder="Ej: Reducir el churn en 15% en los primeros 6 meses..."
                                                value={obj}
                                                onChange={e => updateItem(setKeyObjectives, keyObjectives, idx, e.target.value)}
                                            />
                                            <button onClick={() => removeItem(setKeyObjectives, keyObjectives, idx)} className="text-slate-300 hover:text-rose-500">
                                                <span className="material-symbols-outlined text-[20px]">delete</span>
                                            </button>
                                        </div>
                                    ))}
                                    <button
                                        onClick={() => addItem(setKeyObjectives, keyObjectives)}
                                        className="flex items-center gap-2 text-sm text-primary font-medium hover:text-primary/80 transition-colors px-1 mt-1"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">add_circle</span>
                                        Agregar objetivo
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default CreateVacancy;
