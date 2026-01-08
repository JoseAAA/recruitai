"use client";

import { useState } from "react";
import Link from "next/link";
import { useJobDescriptionGenerator } from "@/lib/ai";

const CreateVacancy: React.FC = () => {
    const { generate, isGenerating, isAvailable } = useJobDescriptionGenerator();
    const [aiPrompt, setAiPrompt] = useState("");
    const [jobTitle, setJobTitle] = useState("");
    const [department, setDepartment] = useState("");
    const [location, setLocation] = useState("");
    const [modality, setModality] = useState("onsite");
    const [description, setDescription] = useState("");
    const [responsibilities, setResponsibilities] = useState<string[]>(["", ""]);

    const handleGenerateAI = async () => {
        if (!aiPrompt.trim() || !isAvailable) return;
        try {
            const result = await generate(aiPrompt);
            if (result) {
                setDescription(result);
                const titleMatch = result.match(/[Tt]ítulo[:\s]+([^\n]+)/);
                if (titleMatch) setJobTitle(titleMatch[1].trim());
            }
        } catch (err) {
            console.error(err);
        }
    };

    const addResponsibility = () => setResponsibilities([...responsibilities, ""]);
    const updateResponsibility = (idx: number, val: string) => {
        const newArr = [...responsibilities];
        newArr[idx] = val;
        setResponsibilities(newArr);
    };
    const removeResponsibility = (idx: number) => {
        setResponsibilities(responsibilities.filter((_, i) => i !== idx));
    };

    const quickTags = ["Java Developer", "HR Manager", "Sales Rep", "Data Analyst"];

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
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Creación de Vacante
                    </h1>
                </div>
                <div className="flex gap-3">
                    <button className="px-4 py-2 text-sm font-medium text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm">
                        Guardar Borrador
                    </button>
                    <button className="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors shadow-sm flex items-center gap-2">
                        <span>Publicar Vacante</span>
                        <span className="material-symbols-outlined text-[18px]">send</span>
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left Column: AI Assistant */}
                <div className="lg:col-span-4 flex flex-col gap-6">
                    {/* AI Writer */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                        <div className="p-4 bg-gradient-to-r from-slate-50 to-white dark:from-slate-800 dark:to-slate-900 border-b border-slate-100 dark:border-slate-800">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
                                <span className="p-1 rounded bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-400">
                                    <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
                                </span>
                                Redactor IA
                            </h3>
                        </div>
                        <div className="p-5 space-y-4">
                            <div className="space-y-2">
                                <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
                                    Describe el puesto ideal
                                </label>
                                <textarea
                                    className="w-full h-32 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-primary focus:border-transparent resize-none transition-shadow outline-none"
                                    placeholder="Ej: Busco un Product Manager Senior para liderar el equipo de fintech en Ciudad de México..."
                                    value={aiPrompt}
                                    onChange={(e) => setAiPrompt(e.target.value)}
                                />
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {quickTags.map((tag) => (
                                    <button
                                        key={tag}
                                        onClick={() => setAiPrompt((prev) => `${prev} ${tag}`)}
                                        className="px-2 py-1 text-[10px] uppercase font-bold tracking-wider bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                                    >
                                        {tag}
                                    </button>
                                ))}
                            </div>
                            <button
                                onClick={handleGenerateAI}
                                disabled={isGenerating || !isAvailable}
                                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
                            >
                                {isGenerating ? "Generando..." : "Generar Perfil"}
                                <span className="material-symbols-outlined text-[16px]">magic_button</span>
                            </button>
                            {!isAvailable && (
                                <p className="text-xs text-amber-600 dark:text-amber-400 text-center">
                                    IA no disponible. Configura un proveedor en Ajustes.
                                </p>
                            )}
                        </div>
                    </div>

                    {/* File Upload */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm group">
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
                                <span className="p-1 rounded bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400">
                                    <span className="material-symbols-outlined text-[18px]">upload_file</span>
                                </span>
                                Cargar Documento
                            </h3>
                        </div>
                        <div className="p-5">
                            <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 group-hover:border-primary/50 rounded-lg p-6 flex flex-col items-center justify-center text-center bg-slate-50 dark:bg-slate-800/30 hover:bg-slate-100 dark:hover:bg-slate-800/80 transition-all cursor-pointer">
                                <div className="mb-3 p-2 bg-white dark:bg-slate-800 rounded-full shadow-sm text-slate-400 group-hover:text-primary transition-colors">
                                    <span className="material-symbols-outlined text-[24px]">cloud_upload</span>
                                </div>
                                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Arrastra tu PDF o DOCX
                                </p>
                                <p className="text-xs text-slate-500 mt-1">Máximo 10MB</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column: Form */}
                <div className="lg:col-span-8 space-y-6">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-800/50 rounded-t-xl">
                            <div className="flex items-center gap-2">
                                <span className="material-symbols-outlined text-slate-400">edit_note</span>
                                <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                                    Formulario Estructurado
                                </h2>
                            </div>
                            <span className="text-xs font-medium px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
                                Edición Manual
                            </span>
                        </div>
                        <div className="p-6 space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                        Título del Puesto <span className="text-rose-500">*</span>
                                    </label>
                                    <input
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-shadow shadow-sm"
                                        placeholder="Ej: Diseñador UX Senior"
                                        type="text"
                                        value={jobTitle}
                                        onChange={(e) => setJobTitle(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                        Departamento
                                    </label>
                                    <select
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                        value={department}
                                        onChange={(e) => setDepartment(e.target.value)}
                                    >
                                        <option value="">Seleccionar...</option>
                                        <option value="engineering">Ingeniería</option>
                                        <option value="product">Producto</option>
                                        <option value="design">Diseño</option>
                                        <option value="sales">Ventas</option>
                                        <option value="hr">Recursos Humanos</option>
                                    </select>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                        Ubicación
                                    </label>
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-slate-400 text-[18px]">
                                            location_on
                                        </span>
                                        <input
                                            className="w-full pl-9 pr-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                            placeholder="Ciudad, País"
                                            type="text"
                                            value={location}
                                            onChange={(e) => setLocation(e.target.value)}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                        Modalidad
                                    </label>
                                    <select
                                        className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none shadow-sm"
                                        value={modality}
                                        onChange={(e) => setModality(e.target.value)}
                                    >
                                        <option value="onsite">Presencial</option>
                                        <option value="remote">Remoto</option>
                                        <option value="hybrid">Híbrido</option>
                                    </select>
                                </div>
                            </div>

                            <hr className="border-slate-100 dark:border-slate-800" />

                            <div className="space-y-2">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                    Descripción del Puesto
                                </label>
                                <div className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg shadow-sm focus-within:ring-2 focus-within:ring-primary transition-shadow">
                                    <div className="flex items-center gap-1 p-2 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 rounded-t-lg">
                                        <button className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400">
                                            <span className="material-symbols-outlined text-[18px]">format_bold</span>
                                        </button>
                                        <button className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400">
                                            <span className="material-symbols-outlined text-[18px]">format_italic</span>
                                        </button>
                                        <button className="p-1.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-400">
                                            <span className="material-symbols-outlined text-[18px]">format_list_bulleted</span>
                                        </button>
                                    </div>
                                    <textarea
                                        className="w-full px-4 py-3 bg-transparent border-none text-sm text-slate-900 dark:text-white focus:ring-0 h-40 resize-y outline-none"
                                        placeholder="Escribe aquí los detalles del rol..."
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                    />
                                </div>
                            </div>

                            <div className="space-y-3">
                                <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                                    Responsabilidades Principales
                                </label>
                                <div className="space-y-2">
                                    {responsibilities.map((resp, idx) => (
                                        <div key={idx} className="flex items-center gap-2 group">
                                            <span className="material-symbols-outlined text-slate-300 cursor-move text-[18px]">
                                                drag_indicator
                                            </span>
                                            <input
                                                className="flex-1 px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none"
                                                placeholder="Añadir responsabilidad..."
                                                value={resp}
                                                onChange={(e) => updateResponsibility(idx, e.target.value)}
                                            />
                                            <button
                                                onClick={() => removeResponsibility(idx)}
                                                className="text-slate-300 hover:text-rose-500"
                                            >
                                                <span className="material-symbols-outlined text-[20px]">delete</span>
                                            </button>
                                        </div>
                                    ))}
                                    <button
                                        onClick={addResponsibility}
                                        className="flex items-center gap-2 text-sm text-primary font-medium hover:text-primary/80 transition-colors px-1 mt-1"
                                    >
                                        <span className="material-symbols-outlined text-[18px]">add_circle</span>
                                        Agregar ítem
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
