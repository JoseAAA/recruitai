/**
 * Gemini AI Provider - Google Cloud LLM
 * Uses Google Gemini API for AI features
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

export class GeminiProvider implements AIProvider {
    readonly type = 'gemini' as const;
    readonly name = 'Google Gemini';

    private apiKey: string;
    private model: string;

    constructor(config: Partial<AIProviderConfig> = {}) {
        this.apiKey = config.apiKey || '';
        this.model = config.model || 'gemini-1.5-flash';
    }

    async isAvailable(): Promise<boolean> {
        if (!this.apiKey) return false;

        try {
            const response = await fetch(
                `https://generativelanguage.googleapis.com/v1beta/models?key=${this.apiKey}`
            );
            return response.ok;
        } catch {
            return false;
        }
    }

    private async generate(prompt: string, systemInstruction?: string): Promise<string> {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent?key=${this.apiKey}`;

        const body: any = {
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: {
                temperature: 0.7,
                maxOutputTokens: 2048,
            },
        };

        if (systemInstruction) {
            body.systemInstruction = { parts: [{ text: systemInstruction }] };
        }

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(`Gemini error: ${error.error?.message || response.statusText}`);
        }

        const data = await response.json();
        return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
    }

    async generateJobDescription(prompt: string): Promise<string> {
        return this.generate(
            `Genera una descripción de empleo completa basándote en: ${prompt}\n\nIncluye: Título, Departamento, Sobre el rol, Responsabilidades (lista), y Requisitos (lista).`,
            'Eres un especialista senior de Recursos Humanos. Genera descripciones de empleo profesionales y atractivas en español.'
        );
    }

    async analyzeJobDescription(request: JobAnalysisRequest): Promise<JobAnalysisResult> {
        const response = await this.generate(
            `Analiza esta descripción de empleo y responde SOLO con un JSON válido:
{
  "title": "string",
  "department": "string",
  "requiredSkills": ["string"],
  "preferredSkills": ["string"],
  "responsibilities": ["string"],
  "requirements": ["string"],
  "minExperienceYears": number,
  "educationLevel": "string"
}

Descripción: ${request.description}`,
            'Eres un analizador de descripciones de empleo. Responde ÚNICAMENTE con JSON válido, sin texto adicional.'
        );

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]);
            }
            throw new Error('No JSON found');
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
        const response = await this.generate(
            `Compara este candidato con los requisitos y responde SOLO con JSON:
{
  "score": number (0-100),
  "summary": "análisis en español",
  "strengths": ["fortaleza1", "fortaleza2"],
  "gaps": ["brecha1", "brecha2"],
  "recommendation": "strong_match" | "good_match" | "partial_match" | "weak_match"
}

Candidato: ${request.candidateInfo}
Requisitos: ${request.jobRequirements}`,
            'Eres un evaluador de candidatos experto. Responde ÚNICAMENTE con JSON válido.'
        );

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]);
            }
            throw new Error('No JSON found');
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
        return this.generate(request.prompt);
    }
}
