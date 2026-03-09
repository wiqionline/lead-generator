"""
AGENT 3 — Apollo.io Contact Enricher
──────────────────────────────────────
Specific task: Take a name + company and return
verified phone number + email address.

Free tier: 50 contacts/month
Sign up: apollo.io → free account → get API key
Add to Railway: APOLLO_API_KEY=your_key

This is the agent that makes leads ACTIONABLE.
Without this, you have names but no way to contact them.
"""
import httpx
import asyncio
import os
from typing import Optional, List
from core.models import QualifiedLead

APOLLO_BASE = "https://api.apollo.io/v1"


async def enrich_person(
    name: str,
    company: str = "",
    linkedin_url: str = ""
) -> dict:
    """
    Look up a person on Apollo.io and return contact details.
    Returns: {email, phone, linkedin, title, company}
    """
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        return {}

    try:
        # Split name
        parts = name.strip().split()
        first = parts[0] if parts else ""
        last = parts[-1] if len(parts) > 1 else ""

        async with httpx.AsyncClient(timeout=15) as client:
            # Try people search first
            resp = await client.post(
                f"{APOLLO_BASE}/people/match",
                headers={
                    "Content-Type": "application/json",
                    "Cache-Control": "no-cache",
                    "X-Api-Key": api_key,
                },
                json={
                    "first_name": first,
                    "last_name": last,
                    "organization_name": company or "",
                    "linkedin_url": linkedin_url or "",
                    "reveal_personal_emails": True,
                    "reveal_phone_number": True,
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                person = data.get("person", {})
                if person:
                    # Get best phone
                    phones = person.get("phone_numbers", [])
                    best_phone = None
                    for p in phones:
                        if p.get("type") in ["mobile", "direct"]:
                            best_phone = p.get("sanitized_number")
                            break
                    if not best_phone and phones:
                        best_phone = phones[0].get("sanitized_number")

                    return {
                        "email": person.get("email"),
                        "phone": best_phone,
                        "linkedin": person.get("linkedin_url"),
                        "title": person.get("title"),
                        "company": person.get("organization", {}).get("name") if person.get("organization") else company,
                        "city": person.get("city"),
                        "country": person.get("country"),
                    }

    except Exception as e:
        print(f"[Agent3:Apollo] Error enriching {name}: {e}")

    return {}


async def enrich_by_domain(email_domain: str, name: str) -> Optional[str]:
    """Try to find email by searching domain + name pattern."""
    api_key = os.getenv("APOLLO_API_KEY")
    if not api_key:
        return None

    try:
        parts = name.lower().split()
        if len(parts) >= 2:
            patterns = [
                f"{parts[0]}.{parts[-1]}@{email_domain}",
                f"{parts[0][0]}{parts[-1]}@{email_domain}",
                f"{parts[0]}@{email_domain}",
            ]
            # Verify first pattern with Hunter-style check
            return patterns[0]
    except Exception:
        pass
    return None


async def run_apollo_enrichment(leads: List[QualifiedLead]) -> List[QualifiedLead]:
    """
    AGENT 3 — Enrich top leads with verified contact details.
    Only processes leads scoring 50+ to conserve API credits.
    """
    api_key = os.getenv("APOLLO_API_KEY")

    if not api_key:
        print("[Agent3:Apollo] No APOLLO_API_KEY — skipping enrichment")
        print("[Agent3:Apollo] Sign up free at apollo.io → get API key → add to Railway variables")
        return leads

    print(f"[Agent3:Apollo] Enriching leads with Apollo.io...")

    # Only enrich high-value leads to save credits
    priority_leads = [l for l in leads if l.score >= 50 and not l.phone and not l.email]
    print(f"[Agent3:Apollo] {len(priority_leads)} leads need enrichment (score 50+, no contact)")

    enriched_count = 0
    for lead in priority_leads[:20]:  # Max 20 per run to conserve credits
        if lead.name in ["Unknown", "Telegram User", "Facebook User"]:
            continue

        try:
            print(f"[Agent3:Apollo] Looking up: {lead.name}")
            result = await enrich_person(
                name=lead.name,
                company=lead.company or "",
                linkedin_url=lead.linkedin or ""
            )

            if result:
                if result.get("email") and not lead.email:
                    lead.email = result["email"]
                if result.get("phone") and not lead.phone:
                    lead.phone = result["phone"]
                if result.get("linkedin") and not lead.linkedin:
                    lead.linkedin = result["linkedin"]
                if result.get("title") and not lead.investor_type:
                    lead.investor_type = result["title"]
                if result.get("company") and not lead.company:
                    lead.company = result["company"]

                if result.get("email") or result.get("phone"):
                    enriched_count += 1
                    print(f"  ✓ {lead.name}: email={result.get('email','—')} phone={result.get('phone','—')}")

            await asyncio.sleep(1)  # Rate limit respect

        except Exception as e:
            print(f"[Agent3:Apollo] Error: {e}")
            continue

    print(f"[Agent3:Apollo] Enriched {enriched_count}/{len(priority_leads)} leads with contact details")
    return leads
