"use client";

import { useState, useEffect, type ReactNode } from "react";
import { healthApi } from "@/lib/api";

export interface AIProviderConfig {
    provider: string;
    extraction_model: string;
    match_model: string;
    embedding_model: string;
}

export function useAI() {
    const [config, setConfig] = useState<AIProviderConfig | null>(null);
    const [isAvailable, setIsAvailable] = useState(false);

    useEffect(() => {
        healthApi.check()
            .then(res => {
                const d = res.data as any;
                setIsAvailable(true);
                setConfig({
                    provider: d.llm_provider ?? d.provider ?? "ollama",
                    extraction_model: d.extraction_model ?? "",
                    match_model: d.match_model ?? "",
                    embedding_model: d.embedding_model ?? "",
                });
            })
            .catch(() => {
                setIsAvailable(false);
                setConfig(null);
            });
    }, []);

    return { config, isAvailable };
}

/** Passthrough wrapper used by providers.tsx */
export function AIProviderContext({ children }: { children: ReactNode }) {
    return children as React.ReactElement;
}
