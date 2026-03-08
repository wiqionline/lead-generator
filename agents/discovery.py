"""
Discovery Agent — Master Orchestrator
───────────────────────────────────────
Coordinates ALL scrapers and returns unified RawLeads.

Sources:
  1. Google Snippets  — LinkedIn, Facebook, Instagram, Dubizzle,
                        Reddit, Twitter/X, YouTube, Forums, News
  2. Bayut.com        — direct scrape (public)
  3. PropertyFinder   — direct scrape (public)
  4. Events           — Eventbrite, Meetup, Cityscape, Expo,
                        YouTube webinars, Seminars, Exhibitions
  5. Telegram         — public channels (needs API credentials)
"""
import asyncio
from typing import List
from core.models import RawLead

from agents.scraper_google_snippets import run_google_snippets_scraper
from agents.scraper_bayut import run_bayut_scraper
from agents.scraper_propertyfinder import run_propertyfinder_scraper
from agents.scraper_events import run_events_scraper
from agents.scraper_telegram import run_telegram_scraper


async def run_discovery(user_query: str, max_leads: int = 20) -> List[RawLead]:
    """
    Master discovery function.
    Runs all scrapers concurrently and returns deduplicated results.
    """
    print(f"\n[Discovery] ── Starting full discovery pipeline ──")
    print(f"[Discovery] Query: {user_query}")
    print(f"[Discovery] Sources: Google Snippets, Bayut, PropertyFinder, Events, Telegram")

    # ── Run all scrapers concurrently ──────────────────────
    results = await asyncio.gather(
        run_google_snippets_scraper(user_query),
        run_bayut_scraper(user_query),
        run_propertyfinder_scraper(user_query),
        run_events_scraper(user_query),
        run_telegram_scraper(user_query),
        return_exceptions=True
    )

    all_leads: List[RawLead] = []
    source_names = ["google_snippets", "bayut", "propertyfinder", "events", "telegram"]
    source_counts = {}

    for i, result in enumerate(results):
        source = source_names[i]
        if isinstance(result, Exception):
            print(f"[Discovery] {source} failed: {result}")
            source_counts[source] = 0
        elif isinstance(result, list):
            source_counts[source] = len(result)
            all_leads.extend(result)

    # ── Deduplicate by URL ─────────────────────────────────
    seen = set()
    unique_leads = []
    for lead in all_leads:
        key = lead.source_url or lead.raw_text[:80]
        if key not in seen:
            seen.add(key)
            unique_leads.append(lead)

    print(f"\n[Discovery] ── Results by source ──")
    for source, count in source_counts.items():
        status = "✓" if count > 0 else "○"
        print(f"  {status} {source:20s}: {count} signals")
    print(f"  {'TOTAL (unique)':22s}: {len(unique_leads)} signals")

    return unique_leads[:max_leads * 4]
