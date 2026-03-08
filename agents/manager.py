"""
Manager Agent
─────────────
Orchestrates the full 5-stage pipeline.
Handles job tracking, stage updates, and error recovery.
"""
import asyncio
from typing import List
from core.models import PipelineJob, QualifiedLead, RunRequest
from core.database import (
    create_job, update_job_stage, complete_job,
    fail_job, save_leads
)
from agents.discovery import run_discovery
from agents.extraction_qualification import run_extraction, run_qualification
from agents.contact_report import run_contact_finder, run_report_generator

# ── Stage names (used for status tracking) ────────────────
STAGE_DISCOVERY    = "discovery"
STAGE_EXTRACTION   = "extraction"
STAGE_QUALIFICATION = "qualification"
STAGE_CONTACT      = "contact_finder"
STAGE_REPORT       = "report_generator"
STAGE_DONE         = "done"


async def run_pipeline(request: RunRequest) -> PipelineJob:
    """
    Main orchestration function.
    Runs all 5 agents in sequence, tracks progress, handles errors.
    Returns a completed PipelineJob with results saved to database.
    """
    # Create the job record
    job = PipelineJob(query=request.query)
    await create_job(job)
    print(f"\n[Manager] Job {job.job_id} started")
    print(f"[Manager] Query: {request.query}")

    try:
        # ── Stage 1: Discovery ─────────────────────────────
        print(f"\n[Manager] → Stage 1: Discovery")
        await update_job_stage(job.job_id, STAGE_DISCOVERY)
        raw_leads = await run_discovery(request.query, max_leads=request.max_leads)

        if not raw_leads:
            raise ValueError("Discovery found no results. Try a different query.")

        # ── Stage 2: Extraction ────────────────────────────
        print(f"\n[Manager] → Stage 2: Extraction")
        await update_job_stage(job.job_id, STAGE_EXTRACTION)
        extracted = await run_extraction(raw_leads, request.query)

        if not extracted:
            raise ValueError("Could not extract structured data from search results.")

        # ── Stage 3: Qualification ─────────────────────────
        print(f"\n[Manager] → Stage 3: Qualification")
        await update_job_stage(job.job_id, STAGE_QUALIFICATION)
        qualified_leads = await run_qualification(extracted, request.query, request.max_leads)

        # ── Stage 4: Contact Finder ────────────────────────
        print(f"\n[Manager] → Stage 4: Contact Finder")
        await update_job_stage(job.job_id, STAGE_CONTACT)
        enriched_leads = await run_contact_finder(qualified_leads)

        # ── Stage 5: Report Generator ──────────────────────
        print(f"\n[Manager] → Stage 5: Report Generator")
        await update_job_stage(job.job_id, STAGE_REPORT)
        summary = await run_report_generator(enriched_leads, request.query)

        # ── Save results ───────────────────────────────────
        await save_leads(enriched_leads, job.job_id)
        await complete_job(job.job_id, len(enriched_leads))

        job.status = "done"
        job.leads_found = len(enriched_leads)
        job.current_stage = STAGE_DONE

        print(f"\n[Manager] ✓ Job {job.job_id} complete — {len(enriched_leads)} leads saved")
        print(f"[Manager] Summary: {summary[:120]}...")

        return job

    except Exception as e:
        error_msg = str(e)
        print(f"\n[Manager] ✗ Job {job.job_id} failed: {error_msg}")
        await fail_job(job.job_id, error_msg)
        job.status = "failed"
        job.error = error_msg
        return job


async def run_pipeline_background(request: RunRequest, job_id: str) -> None:
    """
    Runs the pipeline in the background (used with FastAPI BackgroundTasks).
    The job_id is pre-created so the API can return it immediately.
    """
    await run_pipeline(request)
