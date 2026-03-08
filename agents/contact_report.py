"""
Contact Finder Agent + Report Generator Agent
──────────────────────────────────────────────
Contact finder uses free public sources.
Report generator uses Claude to write the final summary.
"""
import httpx
import asyncio
import anthropic
import json
import re
from typing import List
from bs4 import BeautifulSoup
from core.models import QualifiedLead
from config.settings import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}

# ══════════════════════════════════════════════════════════
# CONTACT FINDER AGENT
# ══════════════════════════════════════════════════════════

async def find_linkedin(name: str, company: str) -> str | None:
    """Search for LinkedIn profile URL via DuckDuckGo."""
    try:
        query = f"site:linkedin.com/in {name} {company or ''} real estate investor"
        url = "https://html.duckduckgo.com/html/"
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client_http:
            resp = await client_http.post(url, data={"q": query})
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result__url")[:3]:
                link_text = result.get_text(strip=True)
                if "linkedin.com/in/" in link_text:
                    return "https://" + link_text if not link_text.startswith("http") else link_text
    except Exception:
        pass
    return None

async def guess_email(name: str, company: str) -> str | None:
    """
    Attempt to guess professional email using common patterns.
    Only used when company domain is findable.
    """
    if not company:
        return None
    try:
        # Try to find company website
        query = f"{company} official website contact email"
        url = "https://html.duckduckgo.com/html/"
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client_http:
            resp = await client_http.post(url, data={"q": query})
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result__url")[:2]:
                domain_text = result.get_text(strip=True)
                # Extract clean domain
                domain_match = re.search(r"([a-z0-9\-]+\.[a-z]{2,})", domain_text)
                if domain_match:
                    domain = domain_match.group(1)
                    # Skip social media and big sites
                    if any(s in domain for s in ["linkedin", "facebook", "twitter", "google", "youtube"]):
                        continue
                    # Generate likely email patterns from name
                    parts = name.lower().split()
                    if len(parts) >= 2:
                        first, last = parts[0], parts[-1]
                        return f"{first}.{last}@{domain}"
    except Exception:
        pass
    return None

async def run_contact_finder(leads: List[QualifiedLead]) -> List[QualifiedLead]:
    """
    Attempts to find contact info for top leads.
    Only runs on high-score leads to save time and respect rate limits.
    """
    print(f"[ContactFinder] Finding contacts for {len(leads)} leads")

    # Only attempt contact finding for top leads (score >= 70)
    high_priority = [l for l in leads if l.score >= 70]

    for lead in high_priority[:10]:  # Cap at 10 to avoid rate limits
        try:
            # Find LinkedIn
            if not lead.linkedin and lead.name:
                linkedin = await find_linkedin(lead.name, lead.company or "")
                if linkedin:
                    lead.linkedin = linkedin

            # Guess email
            if not lead.email and lead.company:
                email = await guess_email(lead.name, lead.company)
                if email:
                    lead.email = email

            # Small delay between lookups
            await asyncio.sleep(1)

        except Exception as e:
            print(f"[ContactFinder] Error for {lead.name}: {e}")
            continue

    print(f"[ContactFinder] Contact enrichment complete")
    return leads


# ══════════════════════════════════════════════════════════
# REPORT GENERATOR AGENT
# ══════════════════════════════════════════════════════════

async def run_report_generator(
    leads: List[QualifiedLead],
    original_query: str
) -> str:
    """
    Uses Claude to generate an executive summary of the lead run.
    """
    print(f"[ReportGenerator] Generating report for {len(leads)} leads")

    if not leads:
        return "No leads found for this search. Try broadening your query."

    top_leads_summary = []
    for lead in leads[:10]:
        top_leads_summary.append({
            "name": lead.name,
            "company": lead.company,
            "type": lead.investor_type,
            "score": lead.score,
            "interest": lead.interest,
            "location": lead.location,
            "signal": lead.signal,
        })

    prompt = f"""You are a real estate intelligence analyst.

A lead generation pipeline ran for this target profile:
"{original_query}"

Results: {len(leads)} qualified leads found.

Top 10 leads:
{json.dumps(top_leads_summary, indent=2)}

Write a brief executive summary (4–6 sentences) covering:
1. Overall quality of leads found
2. Most promising investor types and locations
3. Key investment signals observed
4. Recommended next steps for outreach

Be direct and specific. Use a professional, confident tone."""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.content[0].text.strip()
        print(f"[ReportGenerator] Report generated")
        return summary
    except Exception as e:
        print(f"[ReportGenerator] Error: {e}")
        return f"Pipeline completed. {len(leads)} leads found and qualified."
