/**
 * AI Provider Types - Interface for multi-provider AI system
 * Supports Ollama (local), OpenAI, and Gemini
 */

export type AIProviderType = 'ollama' | 'openai' | 'gemini';

export interface AIProviderConfig {
    type: AIProviderType;
    apiKey?: string;
    baseUrl?: string;
    model: string;
}

export interface JobAnalysisRequest {
    description: string;
    title?: string;
}

export interface JobAnalysisResult {
    title: string;
    department: string;
    requiredSkills: string[];
    preferredSkills: string[];
    responsibilities: string[];
    requirements: string[];
    minExperienceYears: number;
    educationLevel: string;
}

export interface CandidateMatchRequest {
    candidateId: string;
    jobId: string;
    candidateInfo?: string;
    jobRequirements?: string;
}

export interface CandidateMatchResult {
    score: number;
    summary: string;
    strengths: string[];
    gaps: string[];
    recommendation: 'strong_match' | 'good_match' | 'partial_match' | 'weak_match';
}

export interface AICompletionRequest {
    prompt: string;
    maxTokens?: number;
    temperature?: number;
}

export interface AIProvider {
    readonly type: AIProviderType;
    readonly name: string;

    // Check if provider is available/configured
    isAvailable(): Promise<boolean>;

    // Job description generation
    generateJobDescription(prompt: string): Promise<string>;

    // Analyze job and extract structured data
    analyzeJobDescription(request: JobAnalysisRequest): Promise<JobAnalysisResult>;

    // Candidate-job matching with explanation
    analyzeCandidateMatch(request: CandidateMatchRequest): Promise<CandidateMatchResult>;

    // Generic completion for custom prompts
    complete(request: AICompletionRequest): Promise<string>;
}

// Default configurations for each provider
export const DEFAULT_CONFIGS: Record<AIProviderType, Partial<AIProviderConfig>> = {
    ollama: {
        type: 'ollama',
        baseUrl: 'http://localhost:11434',
        model: 'mistral-nemo',
    },
    openai: {
        type: 'openai',
        model: 'gpt-4o-mini',
    },
    gemini: {
        type: 'gemini',
        model: 'gemini-1.5-flash',
    },
};
