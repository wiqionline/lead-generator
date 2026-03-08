"""
API Routes — Background job processing
Pipeline runs in background, user polls for results.
"""
from fastapi import APIRouter, HTTPException
from core.models import RunRequest, PipelineJob
from core.database import get_job, get_leads, clear_leads, create_job
import asyncio

router = APIRouter()

# Global task store — keeps background tasks alive on Railway
_running_tasks = {}


async def _run_pipeline_background(request: RunRequest, job_id: str):
    """Background pipeline runner — updates DB as it goes."""
    try:
        from agents.manager import run_pipeline
        await run_pipeline(request)
    except Exception as e:
        print(f"[Routes] Background pipeline error: {e}")
        from core.database import fail_job
        await fail_job(job_id, str(e))
    finally:
        # Clean up task reference
        _running_tasks.pop(job_id, None)


@router.post("/run")
async def run_lead_generation(request: RunRequest):
    """
    Start pipeline in background — returns job_id immediately.
    Poll GET /status/{job_id} to check progress.
    Poll GET /leads/{job_id} when status is 'done'.
    """
    job = PipelineJob(query=request.query)
    await create_job(job)

    # Create and store task to prevent garbage collection
    task = asyncio.create_task(
        _run_pipeline_background(request, job.job_id)
    )
    _running_tasks[job.job_id] = task

    return {
        "job_id": job.job_id,
        "status": "started",
        "message": f"Pipeline running in background. Check status at /status/{job.job_id}",
        "check_status": f"/status/{job.job_id}",
        "get_leads": f"/leads/{job.job_id}"
    }


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Check pipeline status — poll every 30 seconds."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/leads")
async def list_leads(job_id: str = None, min_score: int = 0):
    """Get all leads, optionally filtered."""
    leads = await get_leads(job_id)
    if min_score > 0:
        leads = [l for l in leads if l.get("score", 0) >= min_score]
    return {"total": len(leads), "leads": leads}


@router.get("/leads/{job_id}")
async def get_job_leads(job_id: str):
    """Get leads for a specific job."""
    leads = await get_leads(job_id)
    return {"job_id": job_id, "total": len(leads), "leads": leads}


@router.delete("/leads")
async def delete_all_leads():
    await clear_leads()
    return {"message": "All leads and jobs cleared"}


@router.get("/health")
async def health_check():
    active = len(_running_tasks)
    return {
        "status": "ok",
        "service": "AI Lead Generator",
        "active_jobs": active
    }
