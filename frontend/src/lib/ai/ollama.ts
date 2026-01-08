/**
 * Ollama AI Provider - Local LLM
 * Uses Ollama running locally for AI features
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

export class OllamaProvider implements AIProvider {
    readonly type = 'ollama' as const;
    readonly name = 'Ollama (Local)';

    private baseUrl: string;
    private model: string;

    constructor(config: Partial<AIProviderConfig> = {}) {
        this.baseUrl = config.baseUrl || 'http://localhost:11434';
        this.model = config.model || 'mistral-nemo';
    }

    async isAvailable(): Promise<boolean> {
        try {
            const response = await fetch(`${this.baseUrl}/api/tags`, {
                method: 'GET',
            });
            return response.ok;
        } catch {
            return false;
        }
    }

    private async chat(prompt: string, systemPrompt?: string): Promise<string> {
        const response = await fetch(`${this.baseUrl}/api/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: this.model,
                prompt: systemPrompt ? `${systemPrompt}\n\nUser: ${prompt}` : prompt,
                stream: false,
            }),
        });

        if (!response.ok) {
            throw new Error(`Ollama error: ${response.statusText}`);
        }

        const data = await response.json();
        return data.response || '';
    }

    async generateJobDescription(prompt: string): Promise<string> {
        const systemPrompt = `Eres un especialista senior de Recursos Humanos. Genera una descripción de empleo profesional y atractiva en español basándote en esta solicitud. Incluye: Título, Departamento, Sobre el rol, Responsabilidades (lista), y Requisitos (lista).`;

        return this.chat(prompt, systemPrompt);
    }

    async analyzeJobDescription(request: JobAnalysisRequest): Promise<JobAnalysisResult> {
        const systemPrompt = `Analiza esta descripción de empleo y extrae información estructurada. Responde SOLO con un JSON válido con este formato exacto:
{
  "title": "string",
  "department": "string",
  "requiredSkills": ["string"],
  "preferredSkills": ["string"],
  "responsibilities": ["string"],
  "requirements": ["string"],
  "minExperienceYears": number,
  "educationLevel": "string"
}`;

        const response = await this.chat(request.description, systemPrompt);

        try {
            // Try to parse JSON from response
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                return JSON.parse(jsonMatch[0]);
            }
            throw new Error('No JSON found in response');
        } catch {
            // Return default structure if parsing fails
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
        const systemPrompt = `Compara este perfil de candidato con los requisitos del puesto. Responde SOLO con un JSON válido:
{
  "score": number (0-100),
  "summary": "string (análisis en español)",
  "strengths": ["string"],
  "gaps": ["string"],
  "recommendation": "strong_match" | "good_match" | "partial_match" | "weak_match"
}`;

        const prompt = `Candidato: ${request.candidateInfo}\n\nRequisitos del puesto: ${request.jobRequirements}`;
        const response = await this.chat(prompt, systemPrompt);

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
        return this.chat(request.prompt);
    }
}
