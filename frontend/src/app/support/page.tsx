"use client";

import { DashboardLayout } from "@/components/layout/dashboard-layout";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export default function SupportPage() {
    const { user } = useAuth();
    const isAdmin = user?.role === "admin";

    const faqs = [
        {
            question: "¿Cómo subo CVs de candidatos?",
            answer: "Ve a Importar CVs en el menú lateral. Puedes arrastrar archivos PDF o DOCX. El sistema valida el archivo, lo convierte a texto con PyMuPDF (PDFs) o python-docx (DOCX) y extrae los datos estructurados con IA (Gemma 4). Si ya subiste ese CV antes, el sistema lo detecta automáticamente sin duplicar.",
            adminOnly: false,
        },
        {
            question: "¿Cómo creo un perfil de puesto?",
            answer: "Ve a Perfiles de Puesto y haz clic en '+ Nueva Vacante'. Puedes pegar la descripción del puesto y la IA extraerá automáticamente los requisitos, habilidades y nivel de seniority. También puedes configurar el peso de cada criterio de evaluación (habilidades, experiencia, educación) con los sliders de la vacante.",
            adminOnly: false,
        },
        {
            question: "¿Cómo funciona el ranking de candidatos?",
            answer: "Desde el detalle de una vacante, haz clic en 'Analizar con IA' en la sección Ranking IA. El sistema evalúa cada candidato en tres dimensiones (habilidades, experiencia, educación) y calcula un puntaje ponderado. El ranking se guarda automáticamente en la base de datos — puedes cerrarlo y volver a verlo sin perder los resultados. Puedes ordenar la tabla por cualquier columna de puntaje.",
            adminOnly: false,
        },
        {
            question: "¿Los datos salen de mi servidor?",
            answer: "No (con la configuración predeterminada). RecruitAI usa Ollama con Gemma 4 corriendo 100% local con aceleración GPU NVIDIA. Los CVs se procesan en tu servidor y ningún dato se envía a la nube. Si cambias el proveedor a Gemini u OpenAI, los textos de CVs se envían a esos servicios, y se activará el enmascaramiento de datos personales (PII) automáticamente.",
            adminOnly: false,
        },
        {
            question: "¿Qué formatos de CV acepta el sistema?",
            answer: "PDF y DOCX únicamente. El sistema valida no solo la extensión del archivo sino también su contenido real (magic bytes) para asegurarse de que sea un documento auténtico. Archivos dañados, protegidos con contraseña o con extensión incorrecta son rechazados con un mensaje de error claro.",
            adminOnly: false,
        },
        {
            question: "¿Cuáles son los estados de un candidato?",
            answer: "Los candidatos pasan por este flujo: Nuevo → En Revisión → Preseleccionado → Entrevista → Oferta → Contratado / Descartado. Puedes cambiar el estado desde el perfil del candidato usando el botón 'Cambiar Estado'. Los cambios quedan registrados en el historial de notas.",
            adminOnly: false,
        },
        {
            question: "¿Cómo configuro el proveedor o modelo de IA?",
            answer: "Ve a Configuración en el menú lateral (solo admins). Puedes cambiar el proveedor (Ollama local, Gemini o OpenAI), el modelo de extracción/matching (gemma4:e2b recomendado para 6GB VRAM, gemma4:e4b para 8GB+) y el modelo de embeddings. Los cambios se guardan en la base de datos. Para que el backend los aplique debes reiniciarlo: docker restart recruitai-backend.",
            adminOnly: true,
        },
        {
            question: "¿El sistema utiliza GPU?",
            answer: "Sí. Ollama está configurado con NVIDIA CUDA en docker-compose.yml. Al iniciar, los modelos se precargan en VRAM (warmup) para eliminar latencia en el primer análisis. Puedes verificar el uso de GPU con: docker exec recruitai-ollama nvidia-smi",
            adminOnly: true,
        },
        {
            question: "¿Qué medidas de seguridad tiene el sistema?",
            answer: "Todos los endpoints de búsqueda y matching requieren autenticación JWT. Las contraseñas tienen mínimo 8 caracteres. Los archivos subidos se validan por contenido (no solo extensión). Los textos de CVs y los campos de vacante se sanitizan antes de enviarse al LLM para evitar prompt injection. El rate limiting protege el login (10/min) y el registro (5/min).",
            adminOnly: true,
        },
    ];

    const visibleFaqs = isAdmin ? faqs : faqs.filter(f => !f.adminOnly);

    return (
        <DashboardLayout>
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Centro de Soporte</h1>
                    <p className="text-slate-500 dark:text-slate-400 text-sm mt-1">
                        Guía rápida y preguntas frecuentes de RecruitAI.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* ── Left: Quick Actions + System Info ─────────────────── */}
                <div className="space-y-4">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-sm">
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Acciones Rápidas</h3>
                        <div className="space-y-2">
                            {isAdmin && (
                                <Link href="/settings" className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                                    <span className="material-symbols-outlined text-primary text-[20px]">settings</span>
                                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Configurar IA</span>
                                </Link>
                            )}
                            <Link href="/data" className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                                <span className="material-symbols-outlined text-emerald-500 text-[20px]">upload_file</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Importar CVs</span>
                            </Link>
                            <Link href="/jobs" className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                                <span className="material-symbols-outlined text-indigo-500 text-[20px]">work</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Perfiles de Puesto</span>
                            </Link>
                            <Link href="/candidates" className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                                <span className="material-symbols-outlined text-blue-500 text-[20px]">group</span>
                                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Ver Candidatos</span>
                            </Link>
                        </div>
                    </div>

                    {/* Stack del sistema */}
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px] text-primary">memory</span>
                            Stack del Sistema
                        </h3>
                        <div className="space-y-2 text-xs">
                            {[
                                ["Motor IA",       "Ollama (local)"],
                                ["Modelo",         "Gemma 4 E2B"],
                                ["Embeddings",     "nomic-embed-text"],
                                ["GPU",            "NVIDIA CUDA"],
                                ["Documentos",     "PyMuPDF + MarkItDown"],
                                ["Vector DB",      "Qdrant"],
                                ["Base de datos",  "PostgreSQL 15"],
                                ["Almacenamiento", "MinIO (S3)"],
                            ].map(([label, value]) => (
                                <div key={label} className="flex justify-between">
                                    <span className="text-slate-500">{label}</span>
                                    <span className={`font-medium ${label === "GPU" ? "text-emerald-500" : "text-slate-700 dark:text-slate-300"}`}>{value}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Contacto */}
                    <div className="bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800 rounded-xl p-5">
                        <h3 className="text-sm font-bold text-indigo-900 dark:text-indigo-200 mb-2 flex items-center gap-2">
                            <span className="material-symbols-outlined text-[18px]">contact_support</span>
                            ¿Necesitas más ayuda?
                        </h3>
                        <p className="text-xs text-indigo-700 dark:text-indigo-300 leading-relaxed mb-3">
                            Contacta al administrador del sistema para asistencia personalizada.
                        </p>
                        <a
                            href="mailto:admin@recruitai.local"
                            className="text-sm font-medium text-indigo-700 dark:text-indigo-300 hover:underline"
                        >
                            admin@recruitai.local
                        </a>
                    </div>
                </div>

                {/* ── FAQs ──────────────────────────────────────────────── */}
                <div className="lg:col-span-2">
                    <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm">
                        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Preguntas Frecuentes</h3>
                            <span className="text-xs text-slate-400">{visibleFaqs.length} preguntas</span>
                        </div>
                        <div className="divide-y divide-slate-100 dark:divide-slate-700/50">
                            {visibleFaqs.map((faq, i) => (
                                <div key={i} className="p-6">
                                    <h4 className="font-bold text-slate-900 dark:text-white mb-2 flex items-start gap-2">
                                        <span className="material-symbols-outlined text-primary text-[18px] mt-0.5 flex-shrink-0">help</span>
                                        {faq.question}
                                    </h4>
                                    <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed pl-6">
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
