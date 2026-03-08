"""
Extraction Agent + Qualification Agent
───────────────────────────────────────
100% FREE — uses keyword/pattern matching only.
Zero API calls. Zero cost. Works offline.
"""
import re
from typing import List, Optional
from core.models import RawLead, QualifiedLead

# ── Keyword banks ──────────────────────────────────────────

INVESTOR_KEYWORDS = [
    "investor", "investment", "invest", "portfolio", "fund",
    "capital", "equity", "asset", "wealth", "hnwi", "family office",
    "private equity", "venture", "angel", "bought", "purchasing",
    "acquiring", "acquisition", "stake", "shareholder"
]

DUBAI_RE_KEYWORDS = [
    "dubai", "uae", "emirates", "off-plan", "off plan", "offplan",
    "downtown", "marina", "palm", "jumeirah", "business bay",
    "creek", "hills", "emaar", "damac", "nakheel", "meraas",
    "aldar", "sobha", "ellington", "handover", "payment plan",
    "freehold", "rera", "dld", "bayut", "propertyfinder"
]

BUDGET_PATTERNS = [
    (r"\$\s*(\d+)\s*[Mm]", "M_USD"),
    (r"AED\s*(\d[\d,]*)", "AED"),
    (r"(\d+)\s*million", "M"),
    (r"(\d+)M\b", "M"),
    (r"budget.*?(\d+)", "budget"),
]

INVESTOR_TYPES = {
    "family office": "Family Office",
    "institutional": "Institutional",
    "fund": "Fund Manager",
    "hnwi": "HNWI",
    "high net worth": "HNWI",
    "developer": "Developer",
    "broker": "Broker",
    "angel": "Angel Investor",
    "venture": "Venture / RE",
}

LOCATION_HINTS = [
    "london", "uk", "europe", "germany", "france", "switzerland",
    "saudi", "ksa", "riyadh", "kuwait", "qatar", "doha", "bahrain",
    "india", "mumbai", "delhi", "singapore", "hong kong", "china",
    "russia", "moscow", "nigeria", "lagos", "usa", "new york",
    "dubai", "abu dhabi", "uae", "pakistan", "turkey"
]

SIGNAL_PHRASES = [
    "looking to invest", "interested in", "seeking investment",
    "expanding portfolio", "buying property", "off-plan",
    "want to buy", "planning to invest", "searching for",
    "investment opportunity", "jv partner", "joint venture",
    "real estate fund", "property investment", "launching",
    "new development", "capital deployment", "acquiring"
]

PLATFORM_SOURCE_MAP = {
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "dubizzle": "Dubizzle",
    "reddit": "Reddit",
    "twitter_x": "Twitter/X",
    "youtube": "YouTube",
    "bayut": "Bayut",
    "propertyfinder": "PropertyFinder",
    "telegram": "Telegram",
    "web_search": "Web Search",
    "forums_news": "Forum/News",
}


# ══════════════════════════════════════════════════════════
# EXTRACTION AGENT — pure Python, no API
# ══════════════════════════════════════════════════════════

def extract_budget(text: str) -> str:
    """Try to extract a budget estimate from text."""
    text_lower = text.lower()
    for pattern, kind in BUDGET_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).replace(",", "")
            try:
                num = float(val)
                if kind in ("M_USD", "M"):
                    return f"${num:.0f}M"
                elif kind == "AED":
                    approx_usd = num / 3.67 / 1_000_000
                    return f"~${approx_usd:.1f}M (AED {num:,.0f})"
                elif kind == "budget" and num > 0:
                    return f"~${num}M"
            except Exception:
                pass
    return "Unknown"


def extract_location(text: str) -> str:
    """Extract location hint from text."""
    text_lower = text.lower()
    for loc in LOCATION_HINTS:
        if loc in text_lower:
            return loc.title()
    return "Unknown"


def extract_investor_type(text: str) -> str:
    """Detect investor type from text."""
    text_lower = text.lower()
    for keyword, itype in INVESTOR_TYPES.items():
        if keyword in text_lower:
            return itype
    return "Investor"


def extract_signal(text: str) -> str:
    """Find the strongest intent signal in text."""
    text_lower = text.lower()
    for phrase in SIGNAL_PHRASES:
        if phrase in text_lower:
            # Return the surrounding context
            idx = text_lower.find(phrase)
            start = max(0, idx - 10)
            end = min(len(text), idx + len(phrase) + 40)
            return text[start:end].strip()
    # Fallback — return first 80 chars
    return text[:80].strip()


def extract_interest(text: str) -> str:
    """Identify the type of investment interest."""
    text_lower = text.lower()
    if "off-plan" in text_lower or "off plan" in text_lower:
        return "Off-plan Property"
    if "luxury" in text_lower or "branded" in text_lower:
        return "Luxury / Branded Residences"
    if "commercial" in text_lower or "office" in text_lower:
        return "Commercial"
    if "villa" in text_lower:
        return "Villas"
    if "apartment" in text_lower or "flat" in text_lower:
        return "Apartments"
    if "hotel" in text_lower:
        return "Hotel / Hospitality"
    return "Dubai Real Estate"


def extract_name_from_text(text: str, platform: str) -> str:
    """Try to extract a person or company name."""
    # Try capitalized name patterns
    patterns = [
        r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b",  # First Last
        r"([A-Z][A-Za-z\s]+(?:Capital|Holdings|Fund|Group|Partners|Investments|Properties))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 4 and len(candidate) < 50:
                return candidate
    return f"{PLATFORM_SOURCE_MAP.get(platform, platform)} Profile"


async def run_extraction(raw_leads: List[RawLead], original_query: str) -> List[dict]:
    """
    Pure Python extraction — zero API calls, zero cost.
    Parses raw leads into structured dicts using regex + keywords.
    """
    print(f"[Extraction] Processing {len(raw_leads)} raw leads (free mode)")
    extracted = []

    for lead in raw_leads:
        text = lead.raw_text or ""
        text_lower = text.lower()

        # Must have at least one investor signal to be worth extracting
        has_investor = any(kw in text_lower for kw in INVESTOR_KEYWORDS)
        has_dubai_re = any(kw in text_lower for kw in DUBAI_RE_KEYWORDS)

        if not (has_investor or has_dubai_re):
            continue

        extracted.append({
            "name": lead.name if lead.name and lead.name != "Unknown" else extract_name_from_text(text, lead.platform),
            "company": None,
            "investor_type": extract_investor_type(text),
            "interest": extract_interest(text),
            "location": extract_location(text),
            "signal": extract_signal(text),
            "source_url": lead.source_url or "",
            "platform": lead.platform,
            "raw_text": text,
        })

    print(f"[Extraction] Extracted {len(extracted)} structured leads")
    return extracted


# ══════════════════════════════════════════════════════════
# QUALIFICATION AGENT — pure Python scoring, no API
# ══════════════════════════════════════════════════════════

def score_lead(item: dict, query: str) -> tuple[int, str]:
    """
    Score a lead 0-100 based on keyword signals.
    Returns (score, reason).
    """
    score = 0
    reasons = []
    text = (item.get("raw_text", "") + " " + item.get("signal", "")).lower()
    query_lower = query.lower()

    # ── Platform quality bonus ─────────────────────────────
    platform_scores = {
        "linkedin": 20, "telegram": 18, "bayut": 16,
        "propertyfinder": 16, "dubizzle": 14, "facebook": 12,
        "reddit": 10, "twitter_x": 8, "instagram": 8,
        "youtube": 6, "web_search": 8, "forums_news": 10,
    }
    platform = item.get("platform", "web_search")
    p_score = platform_scores.get(platform, 8)
    score += p_score
    reasons.append(f"{platform} source (+{p_score})")

    # ── Investor keyword matches ───────────────────────────
    inv_hits = sum(1 for kw in INVESTOR_KEYWORDS if kw in text)
    inv_bonus = min(inv_hits * 5, 25)
    if inv_bonus > 0:
        score += inv_bonus
        reasons.append(f"{inv_hits} investor keywords (+{inv_bonus})")

    # ── Dubai RE keyword matches ───────────────────────────
    re_hits = sum(1 for kw in DUBAI_RE_KEYWORDS if kw in text)
    re_bonus = min(re_hits * 4, 20)
    if re_bonus > 0:
        score += re_bonus
        reasons.append(f"{re_hits} RE keywords (+{re_bonus})")

    # ── Strong intent signal phrases ──────────────────────
    signal_hits = sum(1 for phrase in SIGNAL_PHRASES if phrase in text)
    sig_bonus = min(signal_hits * 6, 24)
    if sig_bonus > 0:
        score += sig_bonus
        reasons.append(f"{signal_hits} intent signals (+{sig_bonus})")

    # ── Budget mention ─────────────────────────────────────
    budget = extract_budget(item.get("raw_text", ""))
    if budget != "Unknown":
        score += 8
        reasons.append(f"budget mentioned (+8)")

    # ── Query relevance ────────────────────────────────────
    query_words = [w for w in query_lower.split() if len(w) > 3]
    q_hits = sum(1 for w in query_words if w in text)
    q_bonus = min(q_hits * 3, 12)
    if q_bonus > 0:
        score += q_bonus
        reasons.append(f"query match (+{q_bonus})")

    score = min(score, 100)
    reason = ", ".join(reasons[:3]) if reasons else "General match"
    return score, reason


def get_recommended_approach(item: dict, score: int) -> str:
    """Generate a recommended outreach approach based on lead data."""
    itype = item.get("investor_type", "Investor")
    interest = item.get("interest", "Dubai property")
    platform = item.get("platform", "web")

    if score >= 85:
        return f"High priority — reach out directly via {PLATFORM_SOURCE_MAP.get(platform, platform)} referencing their {interest} interest"
    elif score >= 70:
        return f"Send personalized message about {interest} opportunities matching their profile"
    else:
        return f"Add to nurture list — share relevant {interest} market updates"


async def run_qualification(
    extracted_leads: List[dict],
    original_query: str,
    max_leads: int = 20
) -> List[QualifiedLead]:
    """
    Pure Python qualification — zero API calls, zero cost.
    Scores leads using keyword matching and heuristics.
    """
    print(f"[Qualification] Scoring {len(extracted_leads)} leads (free mode)")
    qualified = []

    for item in extracted_leads:
        score, reason = score_lead(item, original_query)

        # Filter out low-quality leads
        if score < 30:
            continue

        budget = extract_budget(item.get("raw_text", ""))

        try:
            lead = QualifiedLead(
                name=item.get("name", "Unknown"),
                company=item.get("company"),
                investor_type=item.get("investor_type", "Investor"),
                interest=item.get("interest", "Dubai Real Estate"),
                location=item.get("location"),
                budget_estimate=budget,
                signal=item.get("signal", "")[:200],
                score=score,
                score_reason=reason,
                source=PLATFORM_SOURCE_MAP.get(item.get("platform", ""), "Web"),
                source_url=item.get("source_url"),
                recommended_approach=get_recommended_approach(item, score),
            )
            qualified.append(lead)
        except Exception as e:
            print(f"[Qualification] Skipping lead: {e}")
            continue

    qualified.sort(key=lambda x: x.score, reverse=True)
    print(f"[Qualification] {len(qualified)} leads qualified")
    return qualified[:max_leads]
