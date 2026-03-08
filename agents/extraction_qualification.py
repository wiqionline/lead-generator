"""
Extraction Agent + Qualification Agent
───────────────────────────────────────
Uses Claude to structure raw data and score leads.
"""
import anthropic
import json
import re
from typing import List, Optional
from core.models import RawLead, QualifiedLead
from config.settings import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# ══════════════════════════════════════════════════════════
# EXTRACTION AGENT
# ══════════════════════════════════════════════════════════

async def run_extraction(raw_leads: List[RawLead], original_query: str) -> List[dict]:
    """
    Uses Claude to extract structured data from raw search results.
    Batches multiple leads in a single API call to save tokens.
    """
    print(f"[Extraction] Processing {len(raw_leads)} raw leads")

    if not raw_leads:
        return []

    # Build batch input — process up to 15 at a time
    batch_text = ""
    for i, lead in enumerate(raw_leads[:15]):
        batch_text += f"\n--- Lead {i+1} ---\n{lead.raw_text}\nSource: {lead.source_url}\n"

    prompt = f"""You are a data extraction specialist for real estate investor leads.

Original search intent: {original_query}

Below are raw search snippets. Extract structured lead data from each one.
Only extract if there is a real person, company, or investor signal present.
Skip generic news articles or irrelevant results.

For each valid lead found, return a JSON object. Return a JSON array of all valid leads.
If none are valid, return an empty array [].

Each lead object must have ONLY these fields:
- name (string): person or company name
- company (string or null): company/fund name
- investor_type (string or null): "HNWI" | "Institutional" | "Family Office" | "Developer" | "Broker" | "Unknown"
- interest (string or null): what they're interested in investing in
- location (string or null): city/country if mentioned
- signal (string): the specific phrase or action that indicates investment intent
- source_url (string): the URL from the snippet

Raw data to process:
{batch_text}

Return ONLY a valid JSON array. No explanation, no markdown, no extra text."""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"```json|```", "", text).strip()
        extracted = json.loads(text)
        print(f"[Extraction] Extracted {len(extracted)} structured leads")
        return extracted if isinstance(extracted, list) else []
    except Exception as e:
        print(f"[Extraction] Error: {e}")
        return []


# ══════════════════════════════════════════════════════════
# QUALIFICATION AGENT
# ══════════════════════════════════════════════════════════

async def run_qualification(
    extracted_leads: List[dict],
    original_query: str,
    max_leads: int = 20
) -> List[QualifiedLead]:
    """
    Uses Claude to score and qualify each extracted lead.
    Returns only leads above a minimum quality threshold.
    """
    print(f"[Qualification] Scoring {len(extracted_leads)} leads")

    if not extracted_leads:
        return []

    leads_json = json.dumps(extracted_leads, indent=2)

    prompt = f"""You are a real estate investment lead qualification specialist.

Target profile requested by the user: "{original_query}"

Score and qualify these investor leads. For each lead, determine:
1. How likely they are to be a genuine real estate investor
2. How closely they match the target profile
3. The best recommended outreach approach

Return a JSON array. Each object must have ALL these fields:
- name (string)
- company (string or null)
- investor_type (string)
- interest (string)
- location (string or null)
- budget_estimate (string): estimate like "$500K–$2M" or "Unknown" based on investor type
- signal (string): why they are a lead
- score (integer 0-100): qualification score
- score_reason (string): 1 sentence explaining the score
- source (string): where they were found
- source_url (string or null)
- recommended_approach (string): 1-sentence outreach strategy for this specific person

Scoring guide:
- 85-100: Strong match, clear investment intent, active signals
- 70-84: Good match, some signals, worth pursuing
- 50-69: Possible match, weak signals, lower priority
- Below 50: Skip

Leads to qualify:
{leads_json}

Return ONLY a valid JSON array sorted by score descending. No markdown, no explanation."""

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        scored = json.loads(text)

        if not isinstance(scored, list):
            return []

        # Convert to QualifiedLead objects, filter low scores
        qualified = []
        for item in scored:
            if item.get("score", 0) >= 50:
                try:
                    lead = QualifiedLead(**{
                        k: item.get(k) for k in QualifiedLead.model_fields
                        if k not in ("id", "created_at", "email", "linkedin", "phone")
                    })
                    lead.source = item.get("source", "web")
                    qualified.append(lead)
                except Exception:
                    continue

        qualified.sort(key=lambda x: x.score, reverse=True)
        print(f"[Qualification] {len(qualified)} leads passed qualification")
        return qualified[:max_leads]

    except Exception as e:
        print(f"[Qualification] Error: {e}")
        return []
