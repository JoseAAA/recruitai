"use client";

/**
 * Banner de intervención humana — DS 115-2025-PCM (Reglamento de IA Perú).
 *
 * El screening de CVs está clasificado como "riesgo alto" en el Anexo del
 * Reglamento. La norma exige que TODA decisión asistida por IA pase por una
 * persona que pueda corregirla, anularla o validarla. Este componente comunica
 * esa garantía al reclutador (y, por extensión, al candidato si se le muestra
 * la explicación) en cada vista que presente un ranking generado por IA.
 *
 * Variantes:
 *  - "ranking"    → vista de matching con scores (Ranking IA por vacante).
 *  - "candidate"  → ficha individual de candidato con score IA.
 *  - "compact"    → versión pequeña para tarjetas dentro de listas.
 *
 * No mostrar términos técnicos (modelo, prompt, tokens). Lenguaje claro,
 * dirigido a RRHH.
 */

type Variant = "ranking" | "candidate" | "compact";

const VARIANT_COPY: Record<Variant, { title: string; body: string; icon: string }> = {
    ranking: {
        title: "La IA sugiere; el reclutador decide.",
        body:
            "El ranking se calcula automáticamente como apoyo a tu evaluación. " +
            "La decisión final de avanzar, entrevistar o descartar a un candidato " +
            "es siempre tuya. Cada ajuste queda registrado para auditoría.",
        icon: "info",
    },
    candidate: {
        title: "Recomendación generada por IA",
        body:
            "El puntaje y la explicación de este candidato fueron producidos por " +
            "el sistema como sugerencia. Revísalos junto con el CV antes de tomar " +
            "una decisión. Tu evaluación humana prevalece sobre la del sistema.",
        icon: "psychology",
    },
    compact: {
        title: "Sugerencia IA — revisión humana obligatoria",
        body: "",
        icon: "info",
    },
};

interface Props {
    variant?: Variant;
    /** Oculta el banner si el reclutador ya lo cerró (persistido por sesión). */
    dismissible?: boolean;
    className?: string;
}

export function AIDecisionBanner({
    variant = "ranking",
    dismissible = false,
    className = "",
}: Props) {
    const { title, body, icon } = VARIANT_COPY[variant];

    if (variant === "compact") {
        return (
            <div
                className={
                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full " +
                    "text-[11px] font-medium bg-blue-500/10 text-blue-700 " +
                    "dark:text-blue-300 border border-blue-500/20 " +
                    className
                }
                role="note"
                aria-label="Sugerencia IA con revisión humana obligatoria"
            >
                <span className="material-symbols-outlined text-[14px]">{icon}</span>
                {title}
            </div>
        );
    }

    return (
        <div
            className={
                "flex items-start gap-3 p-4 rounded-xl " +
                "bg-blue-50 dark:bg-blue-950/30 " +
                "border border-blue-200 dark:border-blue-900/60 " +
                "text-blue-900 dark:text-blue-100 " +
                className
            }
            role="note"
            aria-label="Aviso de intervención humana en decisiones asistidas por IA"
        >
            <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-[24px] flex-shrink-0 mt-0.5">
                {icon}
            </span>
            <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold leading-tight">{title}</p>
                {body && (
                    <p className="text-xs text-blue-800/80 dark:text-blue-200/80 mt-1 leading-relaxed">
                        {body}
                    </p>
                )}
            </div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-blue-600/70 dark:text-blue-300/70 flex-shrink-0 hidden md:block">
                DS 115-2025-PCM
            </span>
        </div>
    );
}

export default AIDecisionBanner;
