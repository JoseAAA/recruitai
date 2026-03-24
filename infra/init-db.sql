-- RecruitAI-Core Database Initialization
-- Creates initial schema for the application

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Job Profiles table
CREATE TABLE IF NOT EXISTS job_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    department VARCHAR(100),
    description TEXT,
    required_skills TEXT[] DEFAULT '{}',
    preferred_skills TEXT[] DEFAULT '{}',
    min_experience_years INTEGER DEFAULT 0,
    education_level VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Candidates table
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    summary TEXT,
    skills TEXT[] DEFAULT '{}',
    raw_text TEXT,
    file_path VARCHAR(500),
    file_hash VARCHAR(64),
    status VARCHAR(20) DEFAULT 'new',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Experience entries
CREATE TABLE IF NOT EXISTS experience_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    company VARCHAR(255),
    title VARCHAR(255),
    start_date DATE,
    end_date DATE,
    description TEXT,
    is_current BOOLEAN DEFAULT FALSE
);

-- Education entries
CREATE TABLE IF NOT EXISTS education_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    institution VARCHAR(255),
    degree VARCHAR(255),
    field_of_study VARCHAR(255),
    start_date DATE,
    end_date DATE,
    gpa VARCHAR(10)
);

-- Match results (cached scores)
CREATE TABLE IF NOT EXISTS match_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES job_profiles(id) ON DELETE CASCADE,
    overall_score FLOAT NOT NULL,
    experience_score FLOAT,
    education_score FLOAT,
    skills_score FLOAT,
    explanation TEXT,
    missing_skills TEXT[] DEFAULT '{}',
    bonus_skills TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(candidate_id, job_id)
);

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) DEFAULT 'recruiter',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_job_profiles_status ON job_profiles(status);
CREATE INDEX IF NOT EXISTS idx_match_results_job ON match_results(job_id);
CREATE INDEX IF NOT EXISTS idx_match_results_score ON match_results(overall_score DESC);

-- Candidate notes for HR tracking
CREATE TABLE IF NOT EXISTS candidate_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    note_type VARCHAR(50) DEFAULT 'general',  -- general, interview, feedback, status_change
    content TEXT NOT NULL,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candidate_notes_candidate ON candidate_notes(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_notes_created ON candidate_notes(created_at DESC);

-- Add rating column to candidates if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='candidates' AND column_name='rating') THEN
        ALTER TABLE candidates ADD COLUMN rating INTEGER CHECK (rating >= 1 AND rating <= 5);
    END IF;
END $$;

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_candidates_updated_at BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_job_profiles_updated_at BEFORE UPDATE ON job_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Cloud connections for OAuth integrations (OneDrive, Google Drive)
CREATE TABLE IF NOT EXISTS cloud_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('onedrive', 'google_drive')),
    folder_path VARCHAR(500),
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_sync TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cloud_connections_user ON cloud_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_cloud_connections_provider ON cloud_connections(user_id, provider);

CREATE TRIGGER update_cloud_connections_updated_at BEFORE UPDATE ON cloud_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Migration: Add job_id to candidates (nullable, CASCADE so deleting a job removes its CVs)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='candidates' AND column_name='job_id') THEN
        ALTER TABLE candidates ADD COLUMN job_id UUID REFERENCES job_profiles(id) ON DELETE CASCADE;
        CREATE INDEX idx_candidates_job_id ON candidates(job_id);
    END IF;
END $$;

-- Migration: Fix job_id FK from SET NULL → CASCADE on existing databases
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT tc.constraint_name INTO constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
    JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
    WHERE tc.table_name = 'candidates'
      AND kcu.column_name = 'job_id'
      AND rc.delete_rule = 'SET NULL';

    IF constraint_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE candidates DROP CONSTRAINT ' || quote_ident(constraint_name);
        ALTER TABLE candidates ADD CONSTRAINT candidates_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES job_profiles(id) ON DELETE CASCADE;
    END IF;
END $$;

-- Migration: Add scoring_config to job_profiles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='job_profiles' AND column_name='scoring_config') THEN
        ALTER TABLE job_profiles ADD COLUMN scoring_config JSONB;
    END IF;
END $$;

-- Migration: Add scores_json to match_results for dynamic scoring
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='match_results' AND column_name='scores_json') THEN
        ALTER TABLE match_results ADD COLUMN scores_json JSONB;
    END IF;
END $$;

-- Migration: Add responsibilities to job_profiles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='job_profiles' AND column_name='responsibilities') THEN
        ALTER TABLE job_profiles ADD COLUMN responsibilities TEXT[];
    END IF;
END $$;

-- Migration: Index file_hash for fast deduplication lookups
CREATE INDEX IF NOT EXISTS idx_candidates_file_hash ON candidates(file_hash);

-- Migration: Add seniority, modality, objectives, industry to job_profiles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='job_profiles' AND column_name='seniority_level') THEN
        ALTER TABLE job_profiles ADD COLUMN seniority_level VARCHAR(50);
        ALTER TABLE job_profiles ADD COLUMN work_modality VARCHAR(50);
        ALTER TABLE job_profiles ADD COLUMN key_objectives TEXT[];
        ALTER TABLE job_profiles ADD COLUMN industry VARCHAR(100);
    END IF;
END $$;

-- Migration: Add location to job_profiles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='job_profiles' AND column_name='location') THEN
        ALTER TABLE job_profiles ADD COLUMN location VARCHAR(200);
    END IF;
END $$;

-- Audit log table for LPDP Perú compliance
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    ip_address VARCHAR(50),
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- System settings table (non-sensitive config: provider selection, model names, etc.)
CREATE TABLE IF NOT EXISTS system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Migration: Add recommendation, candidate_name, scored_at to match_results
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='match_results' AND column_name='recommendation') THEN
        ALTER TABLE match_results ADD COLUMN recommendation VARCHAR(50);
        ALTER TABLE match_results ADD COLUMN candidate_name VARCHAR(255);
        ALTER TABLE match_results ADD COLUMN scored_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;
END $$;
