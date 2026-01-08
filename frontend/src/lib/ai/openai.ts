/**
 * OpenAI Provider - Cloud LLM
 * Uses OpenAI API for AI features
 */

import {
    AIProvider,
    AIProviderConfig,
    AICompletionRequest,
    JobAnalysisRequest,
    JobAnalysisResult,
    CandidateMatchRequest,
    CandidateMatchResult,
} from './types';

export class OpenAIProvider implements AIProvider {
    readonly type = 'openai' as const;
    readonly name = 'OpenAI';

    private apiKey: string;
    private model: string;
    private baseUrl: string;

    constructor(config: Partial<AIProviderConfig> = {}) {
        this.apiKey = config.apiKey || '';
        this.model = config.model || 'gpt-4o-mini';
        this.baseUrl = config.baseUrl || 'https://api.openai.com/v1';
    }

    async isAvailable(): Promise<boolean> {
        if (!this.apiKey) return false;

        try {
            const response = await fetch(`${this.baseUrl}/models`, {
                headers: { Authorization: `Bearer ${this.apiKey}` },
            });
            return response.ok;
        } catch {
            return false;
        }
    }

    private async chat(messages: Array<{ role: string; content: string }>, jsonMode = false): Promise<string> {
        const response = await fetch(`${this.baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${this.apiKey}`,
            },
            body: JSON.stringify({
                model: this.model,
                messages,
                temperature: 0.7,
                ...(jsonMode && { response_format: { type: 'json_object' } }),
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`OpenAI error: ${error.error?.message || response.statusText}`);
        }

        const data = await response.json();
        return data.choices?.[0]?.message?.content || '';
    }

    async generateJobDescription(prompt: string): Promise<string> {
        return this.chat([
            {
                role: 'system',
                content: 'Eres un especialista senior de Recursos Humanos. Genera descripciones de empleo profesionales y atractivas en español.',
            },
            {
                role: 'user',
                content: `Genera una descripción de empleo completa basándote en: ${prompt}\n\nIncluye: Título, Departamento, Sobre el rol, Responsabilidades (lista), y Requisitos (lista).`,
            },
        ]);
    }

    async analyzeJobDescription(request: JobAnalysisRequest): Promise<JobAnalysisResult> {
        const response = await this.chat([
            {
                role: 'system',
                content: 'Eres un analizador de descripciones de empleo. Extrae información estructurada y responde en JSON.',
            },
            {
                role: 'user',
                content: `Analiza esta descripción y extrae: title, department, requiredSkills[], preferredSkills[], responsibilities[], requirements[], minExperienceYears (número), educationLevel.\n\nDescripción: ${request.description}`,
            },
        ], true);

        try {
            return JSON.parse(response);
        } catch {
            return {
                title: request.title || 'Sin título',
                department: 'General',
                requiredSkills: [],
                preferredSkills: [],
                responsibilities: [],
                requirements: [],
                minExperienceYears: 0,
                educationLevel: 'bachelor',
            };
        }
    }

    async analyzeCandidateMatch(request: CandidateMatchRequest): Promise<CandidateMatchResult> {
        const response = await this.chat([
            {
                role: 'system',
                content: 'Eres un evaluador de candidatos. Compara perfiles con requisitos y responde en JSON con: score (0-100), summary (español), strengths[], gaps[], recommendation (strong_match|good_match|partial_match|weak_match).',
            },
            {
                role: 'user',
                content: `Candidato: ${request.candidateInfo}\n\nRequisitos: ${request.jobRequirements}`,
            },
        ], true);

        try {
            return JSON.parse(response);
        } catch {
            return {
                score: 50,
                summary: 'No se pudo completar el análisis.',
                strengths: [],
                gaps: [],
                recommendation: 'partial_match',
            };
        }
    }

    async complete(request: AICompletionRequest): Promise<string> {
        return this.chat([{ role: 'user', content: request.prompt }]);
    }
}
