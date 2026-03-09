"""
Discovery Agent — Master Orchestrator v7
─────────────────────────────────────────
Two-tier discovery:

TIER 1 — ORGANIC (real people with real intent):
  - Telegram group monitor (buyer intent messages)
  - Facebook group monitor (buyer intent posts)

TIER 2 — SUPPLEMENTARY (context + signals):
  - Google Snippets (LinkedIn, forums, news)
  - Bayut.com direct scrape
  - PropertyFinder direct scrape
  - Events/Expo/Webinar signals
"""
import asyncio
from typing import List
from core.models import RawLead

from agents.monitor_telegram import run_telegram_monitor
from agents.monitor_facebook import run_facebook_monitor
from agents.scraper_google_snippets import run_google_snippets_scraper
from agents.scraper_bayut import run_bayut_scraper
from agents.scraper_propertyfinder import run_propertyfinder_scraper
from agents.scraper_events import run_events_scraper


async def run_discovery(user_query: str, max_leads: int = 20) -> List[RawLead]:
    print(f"\n[Discovery] ── Starting full discovery pipeline ──")
    print(f"[Discovery] Query: {user_query}")

    # ── TIER 1: Organic monitors (highest quality) ─────────
    print(f"[Discovery] Running organic monitors...")
    organic_results = await asyncio.gather(
        run_telegram_monitor(user_query),
        run_facebook_monitor(user_query),
        return_exceptions=True
    )

    # ── TIER 2: Supplementary scrapers ────────────────────
    print(f"[Discovery] Running supplementary scrapers...")
    supp_results = await asyncio.gather(
        run_google_snippets_scraper(user_query),
        run_bayut_scraper(user_query),
        run_propertyfinder_scraper(user_query),
        run_events_scraper(user_query),
        return_exceptions=True
    )

    all_leads: List[RawLead] = []
    source_counts = {}

    source_names = ["telegram", "facebook", "google_snippets", "bayut", "propertyfinder", "events"]
    all_results = list(organic_results) + list(supp_results)

    for i, result in enumerate(all_results):
        source = source_names[i]
        if isinstance(result, Exception):
            print(f"[Discovery] {source} failed: {result}")
            source_counts[source] = 0
        elif isinstance(result, list):
            source_counts[source] = len(result)
            all_leads.extend(result)

    # ── Deduplicate ────────────────────────────────────────
    seen = set()
    unique = []
    for lead in all_leads:
        key = lead.source_url or lead.raw_text[:80]
        if key not in seen:
            seen.add(key)
            unique.append(lead)

    # ── Prioritise organic leads ───────────────────────────
    # Put Telegram and Facebook leads first
    organic = [l for l in unique if l.platform in ("telegram", "facebook_group")]
    supplementary = [l for l in unique if l.platform not in ("telegram", "facebook_group")]
    sorted_leads = organic + supplementary

    print(f"\n[Discovery] ── Results ──")
    for source, count in source_counts.items():
        tier = "★ ORGANIC" if source in ("telegram", "facebook") else "  supplementary"
        print(f"  {tier} {source:20s}: {count} signals")
    print(f"  {'TOTAL (unique)':32s}: {len(sorted_leads)} signals")
    print(f"  {'Organic leads':32s}: {len(organic)}")
    print(f"  {'Supplementary leads':32s}: {len(supplementary)}")

    return sorted_leads[:max_leads * 4]
