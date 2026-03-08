from supabase import create_client, Client
from config.settings import settings
from core.models import QualifiedLead, PipelineJob
from typing import List, Optional
from datetime import datetime

# ── Initialize Supabase client ────────────────────────────
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# ── Job helpers ───────────────────────────────────────────

async def create_job(job: PipelineJob) -> None:
    try:
        supabase.table("pipeline_jobs").insert(job.model_dump()).execute()
    except Exception as e:
        print(f"[DB] create_job error: {e}")

async def update_job_stage(job_id: str, stage: str, status: str = "running") -> None:
    try:
        supabase.table("pipeline_jobs").update({
            "current_stage": stage,
            "status": status
        }).eq("job_id", job_id).execute()
    except Exception as e:
        print(f"[DB] update_job_stage error: {e}")

async def complete_job(job_id: str, leads_found: int) -> None:
    try:
        supabase.table("pipeline_jobs").update({
            "status": "done",
            "current_stage": None,
            "leads_found": leads_found,
            "completed_at": datetime.utcnow().isoformat()
        }).eq("job_id", job_id).execute()
    except Exception as e:
        print(f"[DB] complete_job error: {e}")

async def fail_job(job_id: str, error: str) -> None:
    try:
        supabase.table("pipeline_jobs").update({
            "status": "failed",
            "error": error[:500]
        }).eq("job_id", job_id).execute()
    except Exception as e:
        print(f"[DB] fail_job error: {e}")

async def get_job(job_id: str) -> Optional[dict]:
    try:
        result = supabase.table("pipeline_jobs").select("*").eq("job_id", job_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB] get_job error: {e}")
        return None

async def save_leads(leads: List[QualifiedLead], job_id: str) -> None:
    try:
        rows = []
        for lead in leads:
            row = lead.model_dump()
            row["job_id"] = job_id
            rows.append(row)
        if rows:
            supabase.table("leads").insert(rows).execute()
    except Exception as e:
        print(f"[DB] save_leads error: {e}")

async def get_leads(job_id: Optional[str] = None) -> List[dict]:
    try:
        query = supabase.table("leads").select("*").order("score", desc=True)
        if job_id:
            query = query.eq("job_id", job_id)
        result = query.execute()
        return result.data or []
    except Exception as e:
        print(f"[DB] get_leads error: {e}")
        return []

async def clear_leads() -> None:
    try:
        supabase.table("leads").delete().neq("id", "").execute()
        supabase.table("pipeline_jobs").delete().neq("job_id", "").execute()
    except Exception as e:
        print(f"[DB] clear_leads error: {e}")
