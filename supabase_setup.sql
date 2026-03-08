-- ============================================================
-- Run this SQL in your Supabase SQL Editor ONCE to set up tables
-- Supabase Dashboard → SQL Editor → New Query → Paste → Run
-- ============================================================

-- Jobs tracking table
CREATE TABLE IF NOT EXISTS pipeline_jobs (
    job_id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    current_stage TEXT,
    leads_found INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error TEXT
);

-- Leads table
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES pipeline_jobs(job_id) ON DELETE CASCADE,
    name TEXT,
    company TEXT,
    investor_type TEXT,
    interest TEXT,
    location TEXT,
    budget_estimate TEXT,
    signal TEXT,
    score INTEGER DEFAULT 0,
    score_reason TEXT,
    email TEXT,
    linkedin TEXT,
    phone TEXT,
    source TEXT,
    source_url TEXT,
    recommended_approach TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast score-based sorting
CREATE INDEX IF NOT EXISTS leads_score_idx ON leads(score DESC);
CREATE INDEX IF NOT EXISTS leads_job_idx ON leads(job_id);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE pipeline_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Allow all operations via service key (your backend uses this)
CREATE POLICY "Allow all for service" ON pipeline_jobs FOR ALL USING (true);
CREATE POLICY "Allow all for service" ON leads FOR ALL USING (true);
