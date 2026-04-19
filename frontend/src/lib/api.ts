import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
    baseURL: `${API_BASE_URL}/api`,
    headers: {
        "Content-Type": "application/json",
    },
});

// Always inject the JWT token from localStorage so it survives page refreshes,
// React effect ordering races, and auth-context resets.
// Also remove the default Content-Type header for FormData requests so the
// browser can set multipart/form-data with the correct boundary automatically.
// Without this, the instance-level "application/json" header overrides the
// multipart header and FastAPI receives file=None / form=None → HTTP 400.
api.interceptors.request.use((config) => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (token) {
        config.headers["Authorization"] = `Bearer ${token}`;
    }
    // Axios v1.x uses AxiosHeaders (not a plain object).
    // The correct API to remove a header is .delete(), not the JS delete operator.
    // Without this, Content-Type: application/json is sent even for FormData,
    // and FastAPI cannot parse the multipart body → file=None → HTTP 400.
    if (config.data instanceof FormData) {
        config.headers.delete("Content-Type");
    }
    return config;
});

// Global 401 handler — when the session expires, redirect to login with a
// clear message instead of showing a cryptic "No se pudieron validar las
// credenciales" error inside the page that triggered the call.
// Excluded: the login endpoint itself (a wrong password returns 401 too).
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const isAuthEndpoint = error.config?.url?.includes("/auth/login");
        if (error.response?.status === 401 && !isAuthEndpoint && typeof window !== "undefined") {
            localStorage.removeItem("token");
            window.location.href = "/login?session=expired";
        }
        return Promise.reject(error);
    }
);

// Types
export interface ScoringDimension {
    dimension: string;
    weight: number;
    description?: string;
}

export interface LanguageRequirement {
    idioma: string;
    nivel: string;
    obligatorio: boolean;
}

export interface Candidate {
    id: string;
    full_name: string;
    email?: string;
    phone?: string;
    linkedin?: string;
    summary?: string;
    skills: string[];
    total_experience_years: number;
    status: string;
    job_id?: string;
}

export interface CandidateDetail extends Candidate {
    experience: Array<{
        company: string;
        title: string;
        start_date?: string | null;
        end_date?: string | null;
        is_current?: boolean;
        description?: string;
    }>;
    education: Array<{
        institution: string;
        degree: string;
        field_of_study?: string;
        education_type?: string; // "educacion" | "certificacion"
    }>;
    idiomas?: Array<{
        idioma: string;
        nivel: string;
        certificacion?: string | null;
    }>;
    raw_text?: string;
}

export interface JobProfile {
    id: string;
    title: string;
    department?: string;
    description?: string;
    seniority_level?: string;
    work_modality?: string;
    industry?: string;
    location?: string;
    required_skills: string[];
    preferred_skills: string[];
    responsibilities?: string[];
    key_objectives?: string[];
    min_experience_years: number;
    education_level?: string;
    status: string;
    required_languages?: LanguageRequirement[];
    scoring_config?: ScoringDimension[];
    candidate_count?: number;
}

export interface InterviewQuestion {
    tipo: "validar_logro" | "explorar_brecha" | "validar_inferencia";
    pregunta: string;
}

export interface MatchResult {
    candidate_id: string;
    full_name: string;
    overall_score: number;
    experience_score: number;
    education_score: number;
    skills_score: number;
    dimension_scores?: Record<string, number>;
    explanation: string;
    recommendation: string; // "Altamente recomendado" | "Buena opción" | "Considerar" | "No recomendado"
    missing_skills: string[];
    bonus_skills: string[];
    relevant_experience_years?: number | null; // LLM: years in roles relevant to this job
    guia_entrevista?: InterviewQuestion[];
    scored_at?: string;
}

export interface SearchResult {
    candidate_id: string;
    full_name: string;
    score: number;
    skills: string[];
    experience_years: number;
}

export interface UploadResponse {
    id: string;
    filename: string;
    status: string;
    extracted_name: string | null;
    skills_count: number;
    message: string;
    job_id?: string;
}

// API Functions
export const candidatesApi = {
    list: (page = 1, pageSize = 20, jobId?: string) =>
        api.get<{ items: Candidate[]; total: number }>("/candidates", {
            params: { page, page_size: pageSize, ...(jobId ? { job_id: jobId } : {}) },
        }),

    get: (id: string) => api.get<CandidateDetail>(`/candidates/${id}`),

    upload: (file: File, jobId?: string) => {
        const formData = new FormData();
        formData.append("file", file);
        if (jobId) formData.append("job_id", jobId);
        return api.post<UploadResponse>("/candidates/upload", formData, {
            timeout: 120000, // 2 minutes per file — LLM extraction is slow on CPU
        });
    },

    uploadMultiple: async (
        files: File[],
        jobId?: string,
        onProgress?: (current: number, total: number, filename: string) => void,
        concurrency = 2, // process 2 CVs in parallel; Ollama queues internally
    ): Promise<UploadResponse[]> => {
        const results: UploadResponse[] = new Array(files.length);
        let completed = 0;

        // Process files in parallel batches of `concurrency`
        for (let i = 0; i < files.length; i += concurrency) {
            const batch = files.slice(i, i + concurrency);
            const batchPromises = batch.map(async (file, batchIdx) => {
                const globalIdx = i + batchIdx;
                if (onProgress) onProgress(completed, files.length, file.name);
                try {
                    const response = await candidatesApi.upload(file, jobId);
                    results[globalIdx] = response.data;
                } catch (error: any) {
                    results[globalIdx] = {
                        id: "",
                        filename: file.name,
                        status: "error",
                        extracted_name: null,
                        skills_count: 0,
                        message: error.response?.data?.detail || "Error al procesar",
                    };
                } finally {
                    completed++;
                    if (onProgress) onProgress(completed, files.length, file.name);
                }
            });
            await Promise.all(batchPromises);
        }

        return results;
    },

    delete: (id: string) => api.delete(`/candidates/${id}`),

    updateStatus: (id: string, status: string) =>
        api.patch(`/candidates/${id}/status`, { status }),

    getFile: (id: string, endpoint: "preview" | "download") =>
        api.get(`/candidates/${id}/${endpoint}`, { responseType: "arraybuffer" }),
};

export const jobsApi = {
    list: () => api.get<{ items: JobProfile[]; total: number }>("/jobs"),

    get: (id: string) => api.get<JobProfile>(`/jobs/${id}`),

    create: (data: Partial<JobProfile> & { scoring_config?: ScoringDimension[]; required_languages?: LanguageRequirement[] }) =>
        api.post<JobProfile>("/jobs", data),

    update: (id: string, data: Partial<JobProfile> & { scoring_config?: ScoringDimension[]; required_languages?: LanguageRequirement[] }) =>
        api.put<JobProfile>(`/jobs/${id}`, data),

    delete: (id: string) => api.delete(`/jobs/${id}`),

    updateStatus: (id: string, newStatus: string) =>
        api.patch(`/jobs/${id}/status?new_status=${encodeURIComponent(newStatus)}`),

    analyze: (file?: File, text?: string) => {
        const formData = new FormData();
        if (file) formData.append("file", file);
        if (text) formData.append("description_text", text);
        // Pass headers:{} so axios merges an empty object — combined with the
        // interceptor this guarantees Content-Type is never application/json.
        return api.post("/jobs/analyze", formData, { headers: {} });
    },

    getScoringPresets: () =>
        api.get<{ default: ScoringDimension[] }>("/jobs/scoring-presets"),

    getScores: (jobId: string) =>
        api.get<{ scores: MatchResult[]; total: number; job_id: string }>(`/jobs/${jobId}/scores`),
};

export const searchApi = {
    semantic: (query: string, limit = 20) =>
        api.post<{ results: SearchResult[]; total: number }>("/search/semantic", {
            query,
            limit,
        }),

    hybrid: (query: string, limit = 20) =>
        api.post<{ results: SearchResult[]; total: number }>("/search/hybrid", {
            query,
            limit,
        }),

    match: (jobId: string, limit = 20) =>
        api.post<{ matches: MatchResult[]; total: number }>("/search/match", {
            job_id: jobId,
            limit,
        }),

    compare: (candidateId: string, jobId: string) =>
        api.get(`/search/compare/${candidateId}/${jobId}`),

    stats: () => api.get("/search/stats"),
};

export const healthApi = {
    check: () => api.get("/health"),
};

// Dashboard stats types
export interface DashboardStats {
    total_candidates: number;
    total_jobs: number;
    active_jobs: number;
    new_candidates_this_week: number;
    candidates_by_status: Record<string, number>;
    recent_candidates: Array<{
        id: string;
        full_name: string;
        skills_count: number;
        status: string;
        created_at: string | null;
    }>;
    recent_jobs: Array<{
        id: string;
        title: string;
        status: string;
        required_skills_count: number;
        created_at: string | null;
    }>;
}

export interface TopCandidateMatch {
    candidate_id: string;
    candidate_name: string;
    job_id: string;
    job_title: string;
    match_score: number;
    skills_match: string[];
    missing_skills: string[];
    recommendation: string;
}

export interface TopMatchesResponse {
    top_candidates: TopCandidateMatch[];
    jobs_with_matches: Array<{
        job_id: string;
        job_title: string;
        required_skills: string[];
        top_candidates: Array<{
            candidate_id: string;
            candidate_name: string;
            match_score: number;
            recommendation: string;
        }>;
    }>;
    star_candidates: TopCandidateMatch[];
    total_pending_review: number;
}

export const statsApi = {
    dashboard: () => api.get<DashboardStats>("/stats/dashboard"),
    quick: () => api.get<{ candidates: number; jobs: number; new_this_week: number }>("/stats/quick"),
    topMatches: () => api.get<TopMatchesResponse>("/stats/top-matches"),
};


// Candidate notes types
export interface CandidateNote {
    id: string;
    candidate_id: string;
    note_type: "general" | "interview" | "feedback" | "status_change";
    content: string;
    rating?: number;
    previous_status?: string;
    new_status?: string;
    created_at: string;
    user_name?: string;
}

export interface NoteCreate {
    content: string;
    note_type?: string;
    rating?: number;
    new_status?: string;
}

export const notesApi = {
    list: (candidateId: string) =>
        api.get<{ items: CandidateNote[]; total: number }>(`/candidates/${candidateId}/notes`),

    create: (candidateId: string, note: NoteCreate) =>
        api.post<CandidateNote>(`/candidates/${candidateId}/notes`, note),

    updateRating: (candidateId: string, rating: number) =>
        api.patch(`/candidates/${candidateId}/rating?rating=${rating}`),

    updateStatus: (candidateId: string, status: string, reason?: string) =>
        api.patch(`/candidates/${candidateId}/status`, { status }),
};
