import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export function getScoreColor(score: number): string {
    if (score >= 80) return "text-emerald-400";
    if (score >= 60) return "text-green-400";
    if (score >= 40) return "text-amber-400";
    return "text-rose-400";
}

export function getScoreBgColor(score: number): string {
    if (score >= 80) return "bg-emerald-500/20 border-emerald-500/30";
    if (score >= 60) return "bg-green-500/20 border-green-500/30";
    if (score >= 40) return "bg-amber-500/20 border-amber-500/30";
    return "bg-rose-500/20 border-rose-500/30";
}

export function formatDate(date: string | Date): string {
    return new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    }).format(new Date(date));
}
