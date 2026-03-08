from fastapi import APIRouter, BackgroundTasks, HTTPException
from core.models import RunRequest, PipelineJob
from core.database import get_job, get_leads, clear_leads, create_job
from agents.manager import run_pipeline
import asyncio

router = APIRouter()

# ── Background task wrapper ───────────────────────────────
async def pipeline_task(request: RunRequest, job_id: str):
    """Runs pipeline in background — updates job in database."""
    try:
        await run_pipeline(request)
    except Exception as e:
        print(f"[Routes] Pipeline task error: {e}")

# ── POST /run ─────────────────────────────────────────────
@router.post("/run", response_model=dict)
async def run_lead_generation(
    request: RunRequest,
    background_tasks: BackgroundTasks
):
    """Start a lead generation pipeline. Returns job_id immediately."""
    job = PipelineJob(query=request.query)
    await create_job(job)

    # Add to background tasks — Railway compatible
    background_tasks.add_task(pipeline_task, request, job.job_id)

    return {
        "job_id": job.job_id,
        "status": "started",
        "message": f"Pipeline started. Poll /status/{job.job_id} to check progress."
    }

# ── GET /status/{job_id} ──────────────────────────────────
@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check pipeline status."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# ── GET /leads ────────────────────────────────────────────
@router.get("/leads")
async def list_leads(job_id: str = None, min_score: int = 0):
    """Get all leads, optionally filtered by job_id or min_score."""
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
