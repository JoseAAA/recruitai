import { DashboardLayout } from "@/components/layout/dashboard-layout";
import Link from "next/link";

export default function SupportPage() {
    const faqs = [
        {
            question: "¿Cómo subo CVs de candidatos?",
            answer: "Ve a la sección Candidatos y haz clic en 'Importar CVs'. Puedes arrastrar archivos PDF o DOCX.",
        },
        {
            question: "¿Cómo configuro la IA local?",
            answer: "Ve a Configuración > Proveedor de IA y selecciona Ollama. Asegúrate de tener Ollama instalado.",
        },
        {
            question: "¿Puedo usar OpenAI o Gemini?",
            answer: "Sí, en Configuración puedes elegir entre Ollama (local), OpenAI o Gemini con tu API key.",
        },
    ];

    return (
        <DashboardLayout>
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                        Centro de Soporte
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Ayuda y recursos para usar RecruitAI.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Quick Actions */}
                <div className="space-y-4">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">
                            Acciones Rápidas
                        </h3>
                        <div className="space-y-3">
                            <Link
                                href="/settings"
                                className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            >
                                <span className="material-symbols-outlined text-primary">settings</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Configurar IA
                                </span>
                            </Link>
                            <Link
                                href="/upload"
                                className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            >
                                <span className="material-symbols-outlined text-emerald-500">upload_file</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Subir CVs
                                </span>
                            </Link>
                            <Link
                                href="/jobs/new"
                                className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                            >
                                <span className="material-symbols-outlined text-indigo-500">add_circle</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                                    Crear Vacante
                                </span>
                            </Link>
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
                            {faqs.map((faq, i) => (
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
