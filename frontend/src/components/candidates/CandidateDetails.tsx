"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useCandidateAnalysis } from "@/lib/ai";

interface CandidateDetailsProps {
    candidateId: string;
}

const CandidateDetails: React.FC<CandidateDetailsProps> = ({ candidateId }) => {
    const { analyze, isAnalyzing } = useCandidateAnalysis();
    const [aiSummary, setAiSummary] = useState<string>("");
    const [matchScore, setMatchScore] = useState<number>(94);

    useEffect(() => {
        const performAnalysis = async () => {
            try {
                const mockCandidate =
                    "Sofía Rodríguez, UX Designer with 7 years of experience in Design Systems and Fintech.";
                const mockJob = "Senior Product Designer with React and SaaS experience.";
                const result = await analyze(mockCandidate, mockJob);
                setAiSummary(result.summary);
                setMatchScore(result.score);
            } catch (e) {
                setAiSummary(
                    "Sus fortalezas clave incluyen experiencia sólida en Sistemas de Diseño y liderazgo en equipos ágiles."
                );
            }
        };
        performAnalysis();
    }, [candidateId]);

    const skills = ["Figma", "Sketch", "HTML/CSS", "User Research", "Agile"];

    return (
        <>
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 mb-2">
                <Link href="/candidates" className="hover:text-primary transition-colors">
                    Candidatos
                </Link>
                <span className="material-symbols-outlined text-[16px]">chevron_right</span>
                <span className="text-slate-900 dark:text-white font-medium">
                    Perfil de Candidato
                </span>
            </div>

            {/* Profile Header */}
            <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                    <div className="flex items-center gap-6">
                        <div className="relative">
                            <img
                                alt="Sofía"
                                className="size-24 rounded-full object-cover border-4 border-slate-50 dark:border-slate-700"
                                src={`https://picsum.photos/seed/${candidateId}/100/100`}
                            />
                            <span className="absolute bottom-1 right-1 h-5 w-5 bg-emerald-500 border-4 border-white dark:border-slate-800 rounded-full"></span>
                        </div>
                        <div>
                            <div className="flex items-center gap-3 mb-1">
                                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                                    Sofía Rodríguez
                                </h1>
                                <span className="bg-primary/10 text-primary text-xs font-semibold px-2.5 py-0.5 rounded-full border border-primary/20">
                                    Diseño de Producto
                                </span>
                            </div>
                            <p className="text-slate-500 dark:text-slate-400 font-medium mb-3">
                                Diseñadora UX Senior
                            </p>
                            <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
                                <div className="flex items-center gap-1.5">
                                    <span className="material-symbols-outlined text-[18px]">
                                        location_on
                                    </span>
                                    Madrid, España
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <span className="material-symbols-outlined text-[18px]">
                                        work_history
                                    </span>
                                    7 años exp.
                                </div>
                                <div className="flex items-center gap-1.5 text-emerald-600">
                                    <span className="material-symbols-outlined text-[18px]">paid</span>
                                    55k - 65k EUR
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="flex gap-3 w-full md:w-auto">
                        <button className="flex-1 sm:flex-none px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300">
                            Rechazar
                        </button>
                        <button className="flex-1 sm:flex-none px-5 py-2 bg-primary text-white font-medium rounded-lg hover:bg-blue-600 shadow-sm">
                            Agendar Entrevista
                        </button>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 space-y-6">
                    {/* AI Summary Card */}
                    <div className="bg-indigo-50 dark:bg-[#1e1b4b]/40 border border-indigo-100 dark:border-indigo-900/50 rounded-xl p-5 relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-3 opacity-10">
                            <span className="material-symbols-outlined text-[120px] text-indigo-500">
                                auto_awesome
                            </span>
                        </div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="material-symbols-outlined text-indigo-600 dark:text-indigo-400">
                                    auto_awesome
                                </span>
                                <h2 className="text-sm font-bold uppercase tracking-wider text-indigo-900 dark:text-indigo-200">
                                    Resumen Generado por IA
                                </h2>
                                <span className="bg-white/50 dark:bg-indigo-900/50 px-2 py-0.5 rounded text-[10px] font-bold text-indigo-700 dark:text-indigo-300">
                                    BETA v2.4
                                </span>
                            </div>
                            {isAnalyzing ? (
                                <div className="h-20 flex items-center justify-center">
                                    <span className="animate-pulse text-indigo-600 dark:text-indigo-400 font-medium">
                                        Analizando perfil con IA...
                                    </span>
                                </div>
                            ) : (
                                <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-sm">
                                    Sofía muestra una alineación del{" "}
                                    <strong className="text-indigo-700 dark:text-indigo-300">
                                        {matchScore}%
                                    </strong>{" "}
                                    con el perfil.{" "}
                                    {aiSummary ||
                                        "Sus fortalezas clave incluyen una sólida experiencia en Sistemas de Diseño y liderazgo en equipos ágiles."}
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Experience */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                            <span className="material-symbols-outlined text-slate-400">work</span>
                            Experiencia Laboral
                        </h3>
                        <div className="relative border-l-2 border-slate-100 dark:border-slate-700 ml-3 space-y-8 pb-2">
                            <div className="relative pl-8">
                                <div className="absolute -left-[9px] top-1.5 h-4 w-4 rounded-full border-2 border-primary bg-white dark:bg-slate-800"></div>
                                <div className="flex justify-between mb-2">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white">
                                        Lead Product Designer
                                    </h4>
                                    <span className="text-sm text-slate-500 font-medium">
                                        2020 - Presente
                                    </span>
                                </div>
                                <p className="text-primary text-sm font-medium mb-2">
                                    TechFlow Solutions • Tiempo completo
                                </p>
                                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                                    Liderando el rediseño de la plataforma SaaS principal,
                                    resultando en un aumento del 25% en la retención de usuarios.
                                </p>
                            </div>
                            <div className="relative pl-8">
                                <div className="absolute -left-[9px] top-1.5 h-4 w-4 rounded-full border-2 border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800"></div>
                                <div className="flex justify-between mb-2">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white">
                                        Senior UI/UX Designer
                                    </h4>
                                    <span className="text-sm text-slate-500 font-medium">
                                        2017 - 2020
                                    </span>
                                </div>
                                <p className="text-primary text-sm font-medium mb-2">
                                    CreativePulse Agency • Tiempo completo
                                </p>
                                <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                                    Diseño de interfaces para clientes fintech y e-commerce.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    {/* Contact Details */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">
                            Detalles de Contacto
                        </h3>
                        <div className="space-y-4 text-sm">
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-slate-400">mail</span>
                                <span className="text-slate-700 dark:text-slate-300">
                                    sofia.rodriguez@email.com
                                </span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-slate-400">call</span>
                                <span className="text-slate-700 dark:text-slate-300">
                                    +34 612 345 678
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Skills */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">
                            Habilidades
                        </h3>
                        <div className="flex flex-wrap gap-2">
                            {skills.map((skill) => (
                                <span
                                    key={skill}
                                    className="px-2 py-1 rounded-md bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-xs font-medium border border-purple-100 dark:border-purple-800"
                                >
                                    {skill}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
};

export default CandidateDetails;
