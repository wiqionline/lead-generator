"""
Pipeline Manager — Orchestrates all 6 agents
──────────────────────────────────────────────
AGENT 1 — DLD Transaction Scraper    → Real buyers from property records
AGENT 2 — LinkedIn Intent Scraper    → Investors who posted publicly
AGENT 3 — Apollo.io Enricher         → Verified phone + email
AGENT 4 — Telegram Intent Monitor    → Real buyer messages (zero spam)
AGENT 5 — Lead Scorer                → Quality score 0-100
AGENT 6 — Report Generator           → Clean actionable summary

Facebook group monitor also runs if FB_EMAIL is set.
"""
import asyncio
from core.models import RunRequest, PipelineJob, QualifiedLead
from core.database import (
    create_job, update_job_stage,
    complete_job, fail_job, save_leads
)

# Import all agents
from agents.agent_dld import run_dld_agent
from agents.agent_linkedin import run_linkedin_agent
from agents.agent_telegram_intent import run_telegram_intent_agent
from agents.monitor_facebook import run_facebook_monitor
from agents.agent_scorer import run_scorer_agent
from agents.agent_apollo import run_apollo_enrichment
from agents.agent_reporter import run_reporter_agent


async def run_pipeline(request: RunRequest) -> PipelineJob:
    """
    Full 6-agent pipeline. Runs background, updates DB at each stage.
    """
    job = PipelineJob(query=request.query)
    await create_job(job)
    query = request.query
    max_leads = request.max_leads or 20

    print(f"\n{'='*50}")
    print(f"PIPELINE START: {query}")
    print(f"{'='*50}")

    try:
        # ── STAGE 1: Source Collection ─────────────────────
        await update_job_stage(job.job_id, "collecting_sources")
        print("\n[Pipeline] Stage 1 — Collecting from all sources...")

        # Run all source agents concurrently
        results = await asyncio.gather(
            run_dld_agent(query),           # Agent 1
            run_linkedin_agent(query),      # Agent 2
            run_telegram_intent_agent(query), # Agent 4
            run_facebook_monitor(query),    # Facebook bonus
            return_exceptions=True
        )

        all_raw = []
        agent_names = ["DLD", "LinkedIn", "Telegram", "Facebook"]
        for i, result in enumerate(results):
            if isinstance(result, list):
                print(f"  ✓ {agent_names[i]}: {len(result)} signals")
                all_raw.extend(result)
            else:
                print(f"  ✗ {agent_names[i]}: {result}")

        print(f"\n[Pipeline] Total raw signals: {len(all_raw)}")

        if not all_raw:
            await fail_job(job.job_id, "No signals found from any source")
            job.status = "failed"
            job.error = "No signals found"
            return job

        # ── STAGE 2: Scoring ───────────────────────────────
        await update_job_stage(job.job_id, "scoring_leads")
        print("\n[Pipeline] Stage 2 — Scoring and qualifying...")
        qualified = await run_scorer_agent(all_raw, query, max_leads)
        print(f"  ✓ {len(qualified)} leads qualified")

        # ── STAGE 3: Contact Enrichment ────────────────────
        await update_job_stage(job.job_id, "enriching_contacts")
        print("\n[Pipeline] Stage 3 — Enriching with Apollo.io...")
        enriched = await run_apollo_enrichment(qualified)  # Agent 3

        # ── STAGE 4: Report ────────────────────────────────
        await update_job_stage(job.job_id, "generating_report")
        print("\n[Pipeline] Stage 4 — Generating report...")
        report = await run_reporter_agent(enriched, query)
        print(report)

        # ── STAGE 5: Save to database ──────────────────────
        await update_job_stage(job.job_id, "saving")
        await save_leads(enriched, job.job_id)
        await complete_job(job.job_id, len(enriched))

        print(f"\n{'='*50}")
        print(f"PIPELINE COMPLETE: {len(enriched)} leads saved")
        print(f"{'='*50}\n")

        job.status = "done"
        job.leads_found = len(enriched)
        return job

    except Exception as e:
        print(f"\n[Pipeline] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        await fail_job(job.job_id, str(e))
        job.status = "failed"
        job.error = str(e)
        return job
