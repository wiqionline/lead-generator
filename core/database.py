from supabase import create_client, Client
from config.settings import settings
from core.models import QualifiedLead, PipelineJob
from typing import List, Optional
import json

# ── Initialize Supabase client ────────────────────────────
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# ── SQL to create tables (run once in Supabase SQL editor) ─
SETUP_SQL = """
-- Jobs table
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
    job_id TEXT REFERENCES pipeline_jobs(job_id),
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
"""

# ── Job helpers ───────────────────────────────────────────

async def create_job(job: PipelineJob) -> None:
    supabase.table("pipeline_jobs").insert(job.model_dump()).execute()

async def update_job_stage(job_id: str, stage: str, status: str = "running") -> None:
    supabase.table("pipeline_jobs").update({
        "current_stage": stage,
        "status": status
    }).eq("job_id", job_id).execute()

async def complete_job(job_id: str, leads_found: int) -> None:
    from datetime import datetime
    supabase.table("pipeline_jobs").update({
        "status": "done",
        "current_stage": None,
        "leads_found": leads_found,
        "completed_at": datetime.utcnow().isoformat()
    }).eq("job_id", job_id).execute()

async def fail_job(job_id: str, error: str) -> None:
    supabase.table("pipeline_jobs").update({
        "status": "failed",
        "error": error
    }).eq("job_id", job_id).execute()

async def get_job(job_id: str) -> Optional[dict]:
    result = supabase.table("pipeline_jobs").select("*").eq("job_id", job_id).execute()
    return result.data[0] if result.data else None

# ── Lead helpers ──────────────────────────────────────────

async def save_leads(leads: List[QualifiedLead], job_id: str) -> None:
    rows = []
    for lead in leads:
        row = lead.model_dump()
        row["job_id"] = job_id
        rows.append(row)
    if rows:
        supabase.table("leads").insert(rows).execute()

async def get_leads(job_id: Optional[str] = None) -> List[dict]:
    query = supabase.table("leads").select("*").order("score", desc=True)
    if job_id:
        query = query.eq("job_id", job_id)
    result = query.execute()
    return result.data or []

async def clear_leads() -> None:
    supabase.table("leads").delete().neq("id", "").execute()
    supabase.table("pipeline_jobs").delete().neq("job_id", "").execute()
