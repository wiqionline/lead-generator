"""
Contact Finder Agent + Report Generator Agent
──────────────────────────────────────────────
100% FREE — no API calls.
Contact finder uses DuckDuckGo public search.
Report generator uses Python string formatting.
"""
import httpx
import asyncio
import re
from typing import List
from bs4 import BeautifulSoup
from core.models import QualifiedLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ══════════════════════════════════════════════════════════
# CONTACT FINDER — free DuckDuckGo lookups
# ══════════════════════════════════════════════════════════

async def find_linkedin(name: str, company: str) -> str | None:
    try:
        query = f"site:linkedin.com/in {name} {company or ''} real estate investor"
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:
            resp = await c.post("https://html.duckduckgo.com/html/", data={"q": query})
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result__url")[:3]:
                link = result.get_text(strip=True)
                if "linkedin.com/in/" in link:
                    return "https://" + link if not link.startswith("http") else link
    except Exception:
        pass
    return None


async def guess_email(name: str, company: str) -> str | None:
    if not company:
        return None
    try:
        query = f"{company} official website contact"
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as c:
            resp = await c.post("https://html.duckduckgo.com/html/", data={"q": query})
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result__url")[:2]:
                domain_text = result.get_text(strip=True)
                match = re.search(r"([a-z0-9\-]+\.[a-z]{2,})", domain_text)
                if match:
                    domain = match.group(1)
                    if any(s in domain for s in ["linkedin", "facebook", "twitter", "google"]):
                        continue
                    parts = name.lower().split()
                    if len(parts) >= 2:
                        return f"{parts[0]}.{parts[-1]}@{domain}"
    except Exception:
        pass
    return None


async def run_contact_finder(leads: List[QualifiedLead]) -> List[QualifiedLead]:
    print(f"[ContactFinder] Enriching top leads (free mode)")
    high_priority = [l for l in leads if l.score >= 70]

    for lead in high_priority[:8]:
        try:
            if not lead.linkedin and lead.name:
                linkedin = await find_linkedin(lead.name, lead.company or "")
                if linkedin:
                    lead.linkedin = linkedin
            if not lead.email and lead.company:
                email = await guess_email(lead.name, lead.company)
                if email:
                    lead.email = email
            await asyncio.sleep(1)
        except Exception as e:
            print(f"[ContactFinder] Error for {lead.name}: {e}")
            continue

    print(f"[ContactFinder] Enrichment complete")
    return leads


# ══════════════════════════════════════════════════════════
# REPORT GENERATOR — pure Python, no API
# ══════════════════════════════════════════════════════════

async def run_report_generator(
    leads: List[QualifiedLead],
    original_query: str
) -> str:
    print(f"[ReportGenerator] Generating report for {len(leads)} leads")

    if not leads:
        return "No leads found. Try broadening your search query."

    # Count by source
    source_counts = {}
    for lead in leads:
        source_counts[lead.source] = source_counts.get(lead.source, 0) + 1

    # Count by investor type
    type_counts = {}
    for lead in leads:
        t = lead.investor_type or "Unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    # Top locations
    locations = [l.location for l in leads if l.location and l.location != "Unknown"]
    top_locations = list(dict.fromkeys(locations))[:4]

    # Score distribution
    high = len([l for l in leads if l.score >= 80])
    mid = len([l for l in leads if 60 <= l.score < 80])
    low = len([l for l in leads if l.score < 60])

    sources_str = ", ".join(f"{s} ({c})" for s, c in source_counts.items())
    types_str = ", ".join(f"{t} ({c})" for t, c in type_counts.items())
    locations_str = ", ".join(top_locations) if top_locations else "Various"

    report = f"""Pipeline completed for: "{original_query}"

SUMMARY
───────
Total leads found : {len(leads)}
High priority (80+): {high} leads
Medium (60-79)    : {mid} leads
Lower priority    : {low} leads

SOURCES
───────
{sources_str}

INVESTOR TYPES
──────────────
{types_str}

TOP LOCATIONS
─────────────
{locations_str}

TOP 3 LEADS
───────────"""

    for i, lead in enumerate(leads[:3], 1):
        report += f"""
{i}. {lead.name}
   Score    : {lead.score}/100
   Type     : {lead.investor_type}
   Interest : {lead.interest}
   Signal   : {lead.signal[:100] if lead.signal else 'N/A'}
   Approach : {lead.recommended_approach}"""

    report += "\n\nNEXT STEPS\n──────────\n"
    report += "1. Review high-priority leads and verify profiles manually\n"
    report += "2. Reach out via LinkedIn or email with personalized messages\n"
    report += "3. Reference their specific investment interest in your outreach\n"
    report += "4. Add medium-priority leads to a nurture sequence"

    return report
