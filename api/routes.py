from fastapi import APIRouter, HTTPException
from core.models import RunRequest, PipelineJob
from core.database import get_job, get_leads, clear_leads, create_job, update_job_stage
from agents.manager import run_pipeline
import asyncio

router = APIRouter()

# ── POST /run ─────────────────────────────────────────────
@router.post("/run", response_model=dict)
async def run_lead_generation(request: RunRequest):
    """
    Runs the full pipeline and returns results when complete.
    Synchronous — waits for completion (2-3 minutes max).
    """
    print(f"[Routes] Starting pipeline for: {request.query}")
    try:
        job = await run_pipeline(request)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "leads_found": job.leads_found,
            "error": job.error,
            "message": f"Done! Found {job.leads_found} leads. Call GET /leads?job_id={job.job_id}"
        }
    except Exception as e:
        print(f"[Routes] Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── GET /status/{job_id} ──────────────────────────────────
@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check the status of a pipeline job."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# ── GET /leads ────────────────────────────────────────────
@router.get("/leads")
async def list_leads(job_id: str = None, min_score: int = 0):
    """Get all leads. Filter by job_id or min_score."""
    leads = await get_leads(job_id)
    if min_score > 0:
        leads = [l for l in leads if l.get("score", 0) >= min_score]
    return {"total": len(leads), "leads": leads}

# ── GET /leads/{job_id} ───────────────────────────────────
@router.get("/leads/{job_id}")
async def get_job_leads(job_id: str):
    """Get leads for a specific job."""
    leads = await get_leads(job_id)
    return {"job_id": job_id, "total": len(leads), "leads": leads}

# ── DELETE /leads ─────────────────────────────────────────
@router.delete("/leads")
async def delete_all_leads():
    """Clear all leads and jobs."""
    await clear_leads()
    return {"message": "All leads and jobs cleared"}

# ── GET /health ───────────────────────────────────────────
@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "AI Lead Generator"}
