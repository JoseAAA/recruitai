/**
 * AI Provider Factory and Context Hook
 * Creates and manages AI providers based on configuration
 */

'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AIProvider, AIProviderType, AIProviderConfig, DEFAULT_CONFIGS } from './types';
import { OllamaProvider } from './ollama';
import { OpenAIProvider } from './openai';
import { GeminiProvider } from './gemini';

const STORAGE_KEY = 'recruitai_ai_config';

interface AIContextType {
    provider: AIProvider;
    config: AIProviderConfig;
    isAvailable: boolean;
    isLoading: boolean;
    error: string | null;
    setProviderType: (type: AIProviderType) => void;
    updateConfig: (config: Partial<AIProviderConfig>) => void;
    testConnection: () => Promise<boolean>;
}

const AIContext = createContext<AIContextType | undefined>(undefined);

function createProvider(config: AIProviderConfig): AIProvider {
    switch (config.type) {
        case 'openai':
            return new OpenAIProvider(config);
        case 'gemini':
            return new GeminiProvider(config);
        case 'ollama':
        default:
            return new OllamaProvider(config);
    }
}

function loadConfig(): AIProviderConfig {
    if (typeof window === 'undefined') {
        return { ...DEFAULT_CONFIGS.ollama, type: 'ollama', model: 'mistral-nemo' } as AIProviderConfig;
    }

    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            return JSON.parse(stored);
        }
    } catch {
        // Ignore parse errors
    }

    return { ...DEFAULT_CONFIGS.ollama, type: 'ollama', model: 'mistral-nemo' } as AIProviderConfig;
}

function saveConfig(config: AIProviderConfig) {
    if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    }
}

export function AIProviderContext({ children }: { children: ReactNode }) {
    const [config, setConfig] = useState<AIProviderConfig>(loadConfig);
    const [provider, setProvider] = useState<AIProvider>(() => createProvider(loadConfig()));
    const [isAvailable, setIsAvailable] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Check availability on mount and config change
    useEffect(() => {
        const checkAvailability = async () => {
            setIsLoading(true);
            setError(null);

            try {
                const available = await provider.isAvailable();
                setIsAvailable(available);
                if (!available) {
                    setError(`${provider.name} no está disponible. Verifica la configuración.`);
                }
            } catch (err) {
                setIsAvailable(false);
                setError(`Error conectando con ${provider.name}`);
            } finally {
                setIsLoading(false);
            }
        };

        checkAvailability();
    }, [provider]);

    const setProviderType = (type: AIProviderType) => {
        const newConfig: AIProviderConfig = {
            ...config,
            ...DEFAULT_CONFIGS[type],
            type,
        } as AIProviderConfig;

        setConfig(newConfig);
        setProvider(createProvider(newConfig));
        saveConfig(newConfig);
    };

    const updateConfig = (updates: Partial<AIProviderConfig>) => {
        const newConfig = { ...config, ...updates };
        setConfig(newConfig);
        setProvider(createProvider(newConfig));
        saveConfig(newConfig);
    };

    const testConnection = async (): Promise<boolean> => {
        setIsLoading(true);
        try {
            const available = await provider.isAvailable();
            setIsAvailable(available);
            setError(available ? null : `${provider.name} no responde`);
            return available;
        } catch {
            setIsAvailable(false);
            setError('Error de conexión');
            return false;
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <AIContext.Provider
            value={{
                provider,
                config,
                isAvailable,
                isLoading,
                error,
                setProviderType,
                updateConfig,
                testConnection,
            }}
        >
            {children}
        </AIContext.Provider>
    );
}

export function useAI() {
    const context = useContext(AIContext);
    if (!context) {
        throw new Error('useAI must be used within AIProviderContext');
    }
    return context;
}

// Convenience hooks for common AI operations
export function useJobDescriptionGenerator() {
    const { provider, isAvailable } = useAI();
    const [isGenerating, setIsGenerating] = useState(false);

    const generate = async (prompt: string): Promise<string> => {
        if (!isAvailable) throw new Error('AI provider not available');

        setIsGenerating(true);
        try {
            return await provider.generateJobDescription(prompt);
        } finally {
            setIsGenerating(false);
        }
    };

    return { generate, isGenerating, isAvailable };
}

export function useCandidateAnalysis() {
    const { provider, isAvailable } = useAI();
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    const analyze = async (candidateInfo: string, jobRequirements: string) => {
        if (!isAvailable) throw new Error('AI provider not available');

        setIsAnalyzing(true);
        try {
            return await provider.analyzeCandidateMatch({
                candidateId: '',
                jobId: '',
                candidateInfo,
                jobRequirements,
            });
        } finally {
            setIsAnalyzing(false);
        }
    };

    return { analyze, isAnalyzing, isAvailable };
}
