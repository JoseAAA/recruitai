import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
    baseURL: `${API_BASE_URL}/api`,
    headers: {
        "Content-Type": "application/json",
    },
});

// Types
export interface ScoringDimension {
    dimension: string;
    weight: number;
    description?: string;
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
    scoring_config?: ScoringDimension[];
    candidate_count?: number;
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
            headers: { "Content-Type": "multipart/form-data" },
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

    create: (data: Partial<JobProfile> & { scoring_config?: ScoringDimension[] }) =>
        api.post<JobProfile>("/jobs", data),

    update: (id: string, data: Partial<JobProfile> & { scoring_config?: ScoringDimension[] }) =>
        api.put<JobProfile>(`/jobs/${id}`, data),

    delete: (id: string) => api.delete(`/jobs/${id}`),

    updateStatus: (id: string, newStatus: string) =>
        api.patch(`/jobs/${id}/status?new_status=${encodeURIComponent(newStatus)}`),

    analyze: (file?: File, text?: string) => {
        const formData = new FormData();
        if (file) formData.append("file", file);
        if (text) formData.append("description_text", text);
        return api.post("/jobs/analyze", formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
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

export const statsApi = {
    dashboard: () => api.get<DashboardStats>("/stats/dashboard"),
    quick: () => api.get<{ candidates: number; jobs: number; new_this_week: number }>("/stats/quick"),
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

// Cloud Sync types
export interface CloudConnectionStatus {
    configured: boolean;
    redirect_uri: string;
}

export interface CloudAuthResponse {
    auth_url: string;
    message: string;
}

export interface CloudFolder {
    id: string;
    name: string;
    path: string;
}

export interface CloudConnection {
    id: string;
    provider: string;
    folder_path: string | null;
    is_active: boolean;
    last_sync: string | null;
    created_at: string;
}

export interface CloudSyncResult {
    status: string;
    folder_path: string;
    files_found: number;
    files: { id: string; name: string; size: number; modified: string }[];
    last_sync: string;
}

export const cloudApi = {
    // OneDrive
    getOneDriveStatus: () =>
        api.get<CloudConnectionStatus>("/cloud/onedrive/status"),

    getOneDriveAuthUrl: (userId: string) =>
        api.get<CloudAuthResponse>(`/cloud/onedrive/auth?user_id=${userId}`),

    listOneDriveFolders: (userId: string, path: string = "root") =>
        api.get<{ path: string; folders: CloudFolder[] }>(`/cloud/onedrive/folders?user_id=${userId}&path=${encodeURIComponent(path)}`),

    syncOneDrive: (userId: string, folderPath: string) =>
        api.post<CloudSyncResult>(`/cloud/onedrive/sync?user_id=${userId}`, { folder_path: folderPath }),

    disconnectOneDrive: (userId: string) =>
        api.delete(`/cloud/onedrive/disconnect?user_id=${userId}`),

    // Get all connections for a user
    listConnections: (userId: string) =>
        api.get<{ connections: CloudConnection[] }>(`/cloud/connections?user_id=${userId}`),
};
