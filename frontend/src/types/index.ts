/**
 * TypeScript types for the RecruitAI application
 */

export interface Candidate {
    id: string;
    name: string;
    email: string;
    role: string;
    location: string;
    experience: string;
    experienceYears: number;
    matchScore: number;
    skills: string[];
    avatar?: string;
    phone?: string;
    salaryRange?: string;
    status: 'new' | 'screening' | 'interview' | 'offer' | 'hired' | 'rejected';
}

export interface CandidateExperience {
    id: string;
    title: string;
    company: string;
    type: string;
    startDate: string;
    endDate?: string;
    description: string;
}

export interface Vacancy {
    id: string;
    title: string;
    category: string;
    department: string;
    location: string;
    modality: 'onsite' | 'remote' | 'hybrid';
    timeAgo: string;
    candidatesCount: number;
    health: {
        applied: number;
        interview: number;
        offer: number;
    };
    recruiters: string[];
    status: 'active' | 'paused' | 'closed';
    createdAt: string;
}

export enum NavigationTab {
    Dashboard = 'dashboard',
    Candidates = 'candidates',
    Vacancies = 'vacancies',
    Analytics = 'analytics',
    Settings = 'settings',
    Support = 'support',
}

export interface DashboardStats {
    avgHiringTime: number;
    avgHiringTimeTrend: number;
    candidatesInProcess: number;
    candidatesNew: number;
    funnelProgressRate: number;
    dataIngestionStatus: number;
    airbyteSyncActive: boolean;
}

export interface User {
    id: string;
    email: string;
    full_name: string;
    role: 'admin' | 'recruiter' | 'viewer';
    avatar?: string;
}
