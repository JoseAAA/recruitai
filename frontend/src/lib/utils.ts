import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

/** Consistent score thresholds used across all components. */
export function scoreColor(value: number): { text: string; bar: string } {
    if (value >= 75) return { text: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" };
    if (value >= 55) return { text: "text-blue-600 dark:text-blue-400",    bar: "bg-blue-500" };
    if (value >= 35) return { text: "text-amber-600 dark:text-amber-400",  bar: "bg-amber-500" };
    return            { text: "text-slate-400",                             bar: "bg-slate-300 dark:bg-slate-600" };
}
