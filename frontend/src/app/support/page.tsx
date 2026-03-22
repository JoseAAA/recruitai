"use client";

import { DashboardLayout } from "@/components/layout/dashboard-layout";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function SupportPage() {
    const { user } = useAuth();
    const isAdmin = user?.role === 'admin';

    const faqs = [
        {
            question: "¿Cómo subo CVs de candidatos?",
            answer: "Ve a Importar CVs en el menú lateral. Puedes arrastrar archivos PDF o DOCX. El sistema los convierte a texto usando PyMuPDF4LLM y luego extrae los datos con IA (Gemma3 4B).",
            adminOnly: false,
        },
        {
            question: "¿Cómo creo un perfil de puesto?",
            answer: "Ve a Perfiles de Puesto y haz clic en '+ Nueva Vacante'. Puedes pegar la descripción del puesto y la IA extraerá automáticamente los requisitos, habilidades y nivel de seniority.",
            adminOnly: false,
        },
        {
            question: "¿Cómo funciona el matching de candidatos?",
            answer: "Desde Perfiles de Puesto, selecciona una convocatoria y haz clic en 'Analizar con IA'. El sistema compara las habilidades de cada candidato con los requisitos del puesto y genera un score de compatibilidad.",
            adminOnly: false,
        },
        {
            question: "¿Los datos salen de mi servidor?",
            answer: "No. RecruitAI utiliza Ollama con el modelo Gemma3 4B, que se ejecuta 100% local en tu servidor con aceleración GPU. Los CVs se procesan localmente y ningún dato se envía a la nube.",
            adminOnly: false,
        },
        {
            question: "¿Qué formatos de CV acepta el sistema?",
            answer: "PDF y DOCX. Los PDFs son procesados con PyMuPDF4LLM y los archivos Word con MarkItDown, ambos de forma local sin dependencias externas.",
            adminOnly: false,
        },
        {
            question: "¿Cómo configuro el modelo de IA?",
            answer: "Ve a Configuración en el menú lateral. Puedes cambiar el modelo de extracción (gemma3:4b por defecto), el modelo de embeddings (nomic-embed-text), y la URL de Ollama. Los cambios requieren guardar y reiniciar.",
            adminOnly: true,
        },
        {
            question: "¿El sistema utiliza GPU?",
            answer: "Sí. Ollama está configurado con NVIDIA CUDA. Al arrancar, los modelos se precargan en VRAM (warmup) para reducir la latencia del primer análisis. Puedes verificar con 'nvidia-smi' dentro del contenedor.",
            adminOnly: true,
        },
    ];

    const visibleFaqs = isAdmin ? faqs : faqs.filter(faq => !faq.adminOnly);

    return (
        <DashboardLayout>
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Centro de Soporte
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Guía rápida y preguntas frecuentes de RecruitAI.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left: Quick Actions + System Info */}
                <div className="space-y-4">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                            Acciones Rápidas
                        </h3>
                        <div className="space-y-3">
                            {isAdmin && (
                                <Link
                                    href="/settings"
                                    className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                                >
                                    <span className="material-symbols-outlined text-primary">settings</span>
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                        Configurar IA
                                    </span>
                                </Link>
                            )}
                            <Link
                                href="/data"
                                className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            >
                                <span className="material-symbols-outlined text-emerald-500">upload_file</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Importar CVs
                                </span>
                            </Link>
                            <Link
                                href="/jobs"
                                className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            >
                                <span className="material-symbols-outlined text-indigo-500">work</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Perfiles de Puesto
                                </span>
                            </Link>
                        </div>
                    </div>

                    {/* System Stack Info */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px] text-primary">memory</span>
                            Stack del Sistema
                        </h3>
                        <div className="space-y-2 text-xs text-slate-500">
                            <div className="flex justify-between">
                                <span>Motor IA</span>
                                <span className="font-medium text-slate-700 dark:text-slate-300">Ollama (local)</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Modelo</span>
                                <span className="font-medium text-slate-700 dark:text-slate-300">Gemma3 4B</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Embeddings</span>
                                <span className="font-medium text-slate-700 dark:text-slate-300">nomic-embed-text</span>
                            </div>
                            <div className="flex justify-between">
                                <span>GPU</span>
                                <span className="font-medium text-emerald-500">NVIDIA CUDA</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Documentos</span>
                                <span className="font-medium text-slate-700 dark:text-slate-300">PyMuPDF + MarkItDown</span>
                            </div>
                        </div>
                    </div>

                    <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800 rounded-xl p-5">
                        <h3 className="text-sm font-bold text-indigo-900 dark:text-indigo-200 mb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px]">contact_support</span>
                            ¿Necesitas más ayuda?
                        </h3>
                        <p className="text-xs text-indigo-700 dark:text-indigo-300 leading-relaxed mb-3">
                            Contacta al equipo de soporte para asistencia personalizada.
                        </p>
                        <a
                            href="mailto:soporte@recruitai.com"
                            className="text-sm font-medium text-indigo-700 dark:text-indigo-300 hover:underline"
                        >
                            soporte@recruitai.com
                        </a>
                    </div>
                </div>

                {/* FAQs */}
                <div className="lg:col-span-2">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                Preguntas Frecuentes
                            </h3>
                        </div>
                        <div className="divide-y divide-slate-200 dark:divide-slate-700">
                            {visibleFaqs.map((faq, i) => (
                                <div key={i} className="p-6">
                                    <h4 className="font-bold text-slate-900 dark:text-white mb-2">
                                        {faq.question}
                                    </h4>
                                    <p className="text-sm text-slate-600 dark:text-slate-400">
                                        {faq.answer}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </DashboardLayout>
    );
}
