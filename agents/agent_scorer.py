"""
AGENT 5 — Lead Scorer & Qualifier
────────────────────────────────────
Specific task: Take raw leads and score each one
on a 0-100 scale based on how likely they are to 
be a real investor ready to transact.

Scoring dimensions:
1. Source quality      (where did we find them?)
2. Intent strength     (how clear is buying signal?)
3. Budget signal       (did they mention money?)
4. Contact available   (can we reach them?)
5. Specificity         (do they mention area/developer?)
6. Recency             (is the signal recent?)

Output: Sorted list of QualifiedLeads with scores + approach
"""
import re
from typing import List, Tuple
from core.models import RawLead, QualifiedLead

# Source quality scores
SOURCE_SCORES = {
    "dld": 35,              # Real transaction = highest trust
    "telegram": 28,         # Real person, real message
    "facebook_group": 25,   # Real person, real post
    "linkedin": 22,         # Professional signal
    "eventbrite": 20,       # Attended investment event
    "expo": 20,             # Attended expo
    "meetup": 18,           # Attended meetup
    "bayut": 15,            # Enquired on portal
    "propertyfinder": 15,   # Enquired on portal
    "youtube_webinar": 12,  # Watched webinar
    "event_google": 12,     # Event attendee signal
    "dubizzle": 10,         # Portal signal
    "web_search": 8,        # Generic web
}

# Strong intent phrases
HIGH_INTENT = [
    "my budget", "budget is", "have aed", "i want to buy",
    "looking to invest", "ready to invest", "planning to buy",
    "i am interested", "please recommend", "dm me", "call me",
    "whatsapp me", "contact me", "reach me", "+971", "05",
]

MEDIUM_INTENT = [
    "which area", "which developer", "good roi", "best area",
    "recommend", "advice", "opinion", "looking for",
    "interested in", "off-plan", "payment plan",
]

DUBAI_AREAS = [
    "marina", "downtown", "palm", "jumeirah", "business bay",
    "creek", "hills", "jvc", "jvt", "meydan", "sobha",
    "emaar", "damac", "nakheel", "meraas", "aldar",
]

BUDGET_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:million|m\b)|aed\s*(\d[\d,]+)",
    re.IGNORECASE
)


def extract_budget_value(text: str) -> float:
    """Returns budget in AED millions, 0 if not found."""
    match = BUDGET_PATTERN.search(text)
    if match:
        if match.group(1):
            return float(match.group(1))
        if match.group(2):
            val = float(match.group(2).replace(",", ""))
            return val / 1_000_000
    return 0


def score_lead(raw: RawLead) -> Tuple[int, str, str]:
    """
    Returns (score, reason, recommended_approach)
    """
    score = 0
    reasons = []
    text = (raw.raw_text or "").lower()
    platform = raw.platform or "web_search"

    # 1. Source quality (max 35)
    src_score = SOURCE_SCORES.get(platform, 8)
    score += src_score
    reasons.append(f"{platform}(+{src_score})")

    # 2. Intent strength (max 30)
    high_hits = sum(1 for p in HIGH_INTENT if p in text)
    med_hits = sum(1 for p in MEDIUM_INTENT if p in text)
    intent_score = min(high_hits * 8 + med_hits * 4, 30)
    if intent_score > 0:
        score += intent_score
        reasons.append(f"intent(+{intent_score})")

    # 3. Budget mentioned (max 15)
    budget_val = extract_budget_value(text)
    if budget_val >= 5:
        score += 15
        reasons.append("budget≥5M(+15)")
    elif budget_val >= 2:
        score += 12
        reasons.append("budget≥2M(+12)")
    elif budget_val > 0:
        score += 6
        reasons.append("budget_mentioned(+6)")

    # 4. Contact available (max 10)
    has_phone = bool(re.search(r"\+971|05\d", text))
    has_email = bool(re.search(r"@[a-z]+\.[a-z]{2,}", text))
    if has_phone:
        score += 8
        reasons.append("phone_shared(+8)")
    if has_email:
        score += 5
        reasons.append("email_shared(+5)")

    # 5. Dubai specificity (max 10)
    area_hits = sum(1 for a in DUBAI_AREAS if a in text)
    area_score = min(area_hits * 3, 10)
    if area_score > 0:
        score += area_score
        reasons.append(f"specific_areas(+{area_score})")

    score = min(score, 100)

    # Recommended approach based on score + source
    if score >= 80:
        approach = "🔥 Hot lead — contact within 24hrs via phone/WhatsApp"
    elif score >= 65:
        approach = "Warm lead — send personalised message referencing their specific interest"
    elif score >= 50:
        approach = "Nurture — add to newsletter, share relevant market updates"
    else:
        approach = "Cold — add to database for long-term nurturing"

    reason_str = ", ".join(reasons[:4])
    return score, reason_str, approach


def extract_fields(raw: RawLead) -> dict:
    """Extract structured fields from raw lead text."""
    text = raw.raw_text or ""
    tl = text.lower()

    # Investor type
    itype = "Investor"
    for kw, label in [
        ("family office", "Family Office"), ("fund", "Fund Manager"),
        ("hnwi", "HNWI"), ("high net worth", "HNWI"),
        ("developer", "Developer"), ("broker", "Broker"),
        ("agent", "Agent"), ("advisor", "Advisor"),
        ("ceo", "Executive"), ("founder", "Executive"),
        ("director", "Director"),
    ]:
        if kw in tl:
            itype = label
            break

    # Interest
    interest = "Dubai Real Estate"
    for kw, label in [
        ("off-plan", "Off-Plan"), ("off plan", "Off-Plan"),
        ("villa", "Villas"), ("apartment", "Apartments"),
        ("commercial", "Commercial"), ("luxury", "Luxury"),
        ("hotel", "Hotel/Hospitality"),
    ]:
        if kw in tl:
            interest = label
            break

    # Location
    location = "Unknown"
    for loc in ["london", "india", "saudi", "kuwait", "pakistan",
                "russia", "nigeria", "china", "singapore", "uk",
                "dubai", "abu dhabi", "usa", "europe", "germany"]:
        if loc in tl:
            location = loc.title()
            break

    # Budget
    budget_val = extract_budget_value(text)
    budget_str = f"AED {budget_val}M" if budget_val > 0 else "Unknown"

    # Signal snippet
    signal = ""
    for phrase in ["looking for", "budget", "want to", "interested", "planning"]:
        idx = tl.find(phrase)
        if idx >= 0:
            signal = text[max(0, idx-10):idx+120].strip()
            break
    if not signal:
        signal = text[:120].strip()

    return {
        "investor_type": itype,
        "interest": interest,
        "location": location,
        "budget_estimate": budget_str,
        "signal": signal[:200],
    }


async def run_scorer_agent(
    raw_leads: List[RawLead],
    query: str,
    max_leads: int = 20
) -> List[QualifiedLead]:
    """
    AGENT 5 — Score and qualify all raw leads.
    Returns top leads sorted by score descending.
    """
    print(f"[Agent5:Scorer] Scoring {len(raw_leads)} raw leads...")
    qualified = []

    for raw in raw_leads:
        try:
            score, reason, approach = score_lead(raw)
            if score < 20:
                continue

            fields = extract_fields(raw)

            # Extract phone from raw text if present
            phone_match = re.search(
                r"Phone[:\s]+(\+?\d[\d\s\-]{7,15})", raw.raw_text or ""
            )
            phone = phone_match.group(1).strip() if phone_match else None

            lead = QualifiedLead(
                name=raw.name or "Unknown",
                investor_type=fields["investor_type"],
                interest=fields["interest"],
                location=fields["location"],
                budget_estimate=fields["budget_estimate"],
                signal=fields["signal"],
                score=score,
                score_reason=reason,
                source=raw.platform or "web",
                source_url=raw.source_url,
                recommended_approach=approach,
                phone=phone,
            )
            qualified.append(lead)

        except Exception as e:
            print(f"[Agent5:Scorer] Error: {e}")
            continue

    qualified.sort(key=lambda x: x.score, reverse=True)
    print(f"[Agent5:Scorer] {len(qualified)} qualified → returning top {max_leads}")
    return qualified[:max_leads]
