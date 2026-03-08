"""
Extraction Agent + Qualification Agent
───────────────────────────────────────
100% FREE — uses keyword/pattern matching only.
Zero API calls. Zero cost.
v4 — extracts real names from URLs + better signal parsing
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
    (r"AED\s*(\d[\d,]+)", "AED"),
    (r"\$\s*(\d+)\s*[Mm]", "M_USD"),
    (r"(\d+)\s*million", "M"),
    (r"(\d+)M\b", "M"),
    (r"(\d[\d,]+)\s*AED", "AED"),
]

INVESTOR_TYPES = {
    "family office": "Family Office",
    "institutional": "Institutional",
    "fund": "Fund Manager",
    "hnwi": "HNWI",
    "high net worth": "HNWI",
    "developer": "Developer",
    "broker": "Broker",
    "agent": "Agent/Broker",
    "realtor": "Agent/Broker",
    "angel": "Angel Investor",
    "venture": "Venture / RE",
    "advisor": "Investment Advisor",
    "consultant": "Consultant",
    "ceo": "Executive/Investor",
    "founder": "Executive/Investor",
    "director": "Executive/Investor",
    "manager": "Fund/Asset Manager",
}

LOCATION_HINTS = [
    "london", "uk", "europe", "germany", "france", "switzerland",
    "saudi", "ksa", "riyadh", "kuwait", "qatar", "doha", "bahrain",
    "india", "mumbai", "delhi", "singapore", "hong kong", "china",
    "russia", "moscow", "nigeria", "lagos", "usa", "new york",
    "dubai", "abu dhabi", "uae", "pakistan", "turkey", "canada",
    "australia", "egypt", "jordan", "lebanon", "iran"
]

SIGNAL_PHRASES = [
    "looking to invest", "interested in", "seeking investment",
    "expanding portfolio", "buying property", "off-plan",
    "want to buy", "planning to invest", "searching for",
    "investment opportunity", "jv partner", "joint venture",
    "real estate fund", "property investment", "launching",
    "new development", "capital deployment", "acquiring",
    "aed 2m", "aed 3m", "aed 5m", "2m+", "3m+", "5m+",
    "investors", "off-plan advisor", "property advisor"
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
    "event_google": "Event/Webinar",
    "eventbrite": "Eventbrite",
    "meetup": "Meetup",
    "youtube_webinar": "YouTube Webinar",
    "expo": "Expo/Exhibition",
}


# ══════════════════════════════════════════════════════════
# NAME EXTRACTION — from URLs and text
# ══════════════════════════════════════════════════════════

def extract_name_from_url(url: str) -> Optional[str]:
    """
    Extract real name from social profile URLs.
    linkedin.com/in/john-smith-123 → John Smith
    instagram.com/john.smith → John Smith
    facebook.com/john.smith → John Smith
    """
    if not url:
        return None

    # LinkedIn: /in/firstname-lastname-digits
    li_match = re.search(r"linkedin\.com/in/([a-z0-9\-]+)", url, re.IGNORECASE)
    if li_match:
        slug = li_match.group(1)
        # Remove trailing digits and hyphens
        slug = re.sub(r"-?\d+$", "", slug).strip("-")
        # Convert hyphens to spaces and title case
        parts = [p for p in slug.split("-") if len(p) > 1]
        if parts:
            name = " ".join(p.capitalize() for p in parts[:3])
            if len(name) > 3:
                return name

    # Instagram: /username or /user.name
    ig_match = re.search(r"instagram\.com/([a-z0-9_.]+)", url, re.IGNORECASE)
    if ig_match:
        username = ig_match.group(1).replace(".", " ").replace("_", " ")
        parts = username.split()
        if parts and len(parts[0]) > 2:
            return " ".join(p.capitalize() for p in parts[:2])

    # Facebook: /username or /profile
    fb_match = re.search(r"facebook\.com/(?!groups|pages)([a-z0-9.]+)", url, re.IGNORECASE)
    if fb_match:
        username = fb_match.group(1).replace(".", " ")
        parts = username.split()
        if parts and len(parts[0]) > 2:
            return " ".join(p.capitalize() for p in parts[:2])

    # Twitter/X: /username
    tw_match = re.search(r"(?:twitter|x)\.com/([a-z0-9_]+)", url, re.IGNORECASE)
    if tw_match:
        username = tw_match.group(1).replace("_", " ")
        if len(username) > 2:
            return username.title()

    return None


def extract_name_from_text(text: str) -> Optional[str]:
    """Extract person or company name from raw text."""
    # Pattern: "I'm John Smith" or "My name is John Smith"
    intro_match = re.search(
        r"(?:I[''`]m|I am|My name is|Contact|Call me)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
        text
    )
    if intro_match:
        return intro_match.group(1)

    # Company pattern: XYZ Capital, XYZ Holdings etc
    company_match = re.search(
        r"([A-Z][A-Za-z\s]{2,30}(?:Capital|Holdings|Fund|Group|Partners|Investments|Properties|Realty|Real Estate|Advisory))",
        text
    )
    if company_match:
        return company_match.group(1).strip()

    # Two capitalized words (likely a name)
    name_match = re.search(r"\b([A-Z][a-z]{2,15})\s+([A-Z][a-z]{2,15})\b", text)
    if name_match:
        first, last = name_match.group(1), name_match.group(2)
        # Skip common non-name pairs
        skip = {"Off Plan", "Real Estate", "Dubai Property", "United Arab", "Business Bay"}
        if f"{first} {last}" not in skip:
            return f"{first} {last}"

    return None


def extract_company_from_text(text: str) -> Optional[str]:
    """Extract company name from text."""
    match = re.search(
        r"([A-Z][A-Za-z\s]{2,25}(?:Capital|Holdings|Fund|Group|Partners|Investments|Properties|Realty|LLC|Ltd|FZE|PJSC))",
        text
    )
    if match:
        return match.group(1).strip()
    return None


# ══════════════════════════════════════════════════════════
# OTHER EXTRACTORS
# ══════════════════════════════════════════════════════════

def extract_budget(text: str) -> str:
    for pattern, kind in BUDGET_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).replace(",", "")
            try:
                num = float(val)
                if kind == "AED":
                    if num > 100000:
                        usd = num / 3.67 / 1_000_000
                        return f"~${usd:.1f}M (AED {num:,.0f})"
                elif kind in ("M_USD", "M"):
                    if num > 0:
                        return f"${num:.0f}M"
            except Exception:
                pass
    # Check for range patterns like "2M-5M"
    range_match = re.search(r"(\d+)M[\-–](\d+)M", text, re.IGNORECASE)
    if range_match:
        return f"${range_match.group(1)}M–${range_match.group(2)}M"
    return "Unknown"


def extract_location(text: str) -> str:
    text_lower = text.lower()
    for loc in LOCATION_HINTS:
        if loc in text_lower:
            return loc.title()
    return "Unknown"


def extract_investor_type(text: str) -> str:
    text_lower = text.lower()
    for keyword, itype in INVESTOR_TYPES.items():
        if keyword in text_lower:
            return itype
    return "Investor"


def extract_signal(text: str) -> str:
    text_lower = text.lower()
    for phrase in SIGNAL_PHRASES:
        if phrase in text_lower:
            idx = text_lower.find(phrase)
            start = max(0, idx - 15)
            end = min(len(text), idx + len(phrase) + 60)
            return text[start:end].strip()
    return text[:100].strip()


def extract_interest(text: str) -> str:
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


# ══════════════════════════════════════════════════════════
# EXTRACTION AGENT
# ══════════════════════════════════════════════════════════

async def run_extraction(raw_leads: List[RawLead], original_query: str) -> List[dict]:
    print(f"[Extraction] Processing {len(raw_leads)} raw leads (free mode v4)")
    extracted = []

    for lead in raw_leads:
        text = lead.raw_text or ""
        text_lower = text.lower()
        url = lead.source_url or ""

        has_investor = any(kw in text_lower for kw in INVESTOR_KEYWORDS)
        has_dubai_re = any(kw in text_lower for kw in DUBAI_RE_KEYWORDS)
        if not (has_investor or has_dubai_re):
            continue

        # Try URL first for name (most reliable), then text
        name = (
            extract_name_from_url(url) or
            (lead.name if lead.name and lead.name not in
             ["Unknown", "Linkedin Profile", "Facebook Profile",
              "Bayut Agent/Developer", "PropertyFinder Agent/Developer",
              "Bayut Page", "PropertyFinder Page"] else None) or
            extract_name_from_text(text) or
            f"{PLATFORM_SOURCE_MAP.get(lead.platform, lead.platform)} Contact"
        )

        extracted.append({
            "name": name,
            "company": extract_company_from_text(text),
            "investor_type": extract_investor_type(text),
            "interest": extract_interest(text),
            "location": extract_location(text),
            "signal": extract_signal(text),
            "source_url": url,
            "platform": lead.platform,
            "raw_text": text,
        })

    print(f"[Extraction] Extracted {len(extracted)} structured leads")
    return extracted


# ══════════════════════════════════════════════════════════
# QUALIFICATION AGENT
# ══════════════════════════════════════════════════════════

def score_lead(item: dict, query: str) -> tuple[int, str]:
    score = 0
    reasons = []
    text = (item.get("raw_text", "") + " " + item.get("signal", "")).lower()

    platform_scores = {
        "linkedin": 20, "telegram": 18, "bayut": 16,
        "propertyfinder": 16, "dubizzle": 14, "facebook": 12,
        "reddit": 10, "twitter_x": 8, "instagram": 8,
        "youtube": 6, "web_search": 8, "forums_news": 10,
        "event_google": 18, "eventbrite": 20, "meetup": 16,
        "youtube_webinar": 14, "expo": 22,
    }
    platform = item.get("platform", "web_search")
    p_score = platform_scores.get(platform, 8)
    score += p_score
    reasons.append(f"{platform} source (+{p_score})")

    inv_hits = sum(1 for kw in INVESTOR_KEYWORDS if kw in text)
    inv_bonus = min(inv_hits * 5, 25)
    if inv_bonus > 0:
        score += inv_bonus
        reasons.append(f"{inv_hits} investor keywords (+{inv_bonus})")

    re_hits = sum(1 for kw in DUBAI_RE_KEYWORDS if kw in text)
    re_bonus = min(re_hits * 4, 20)
    if re_bonus > 0:
        score += re_bonus
        reasons.append(f"{re_hits} RE keywords (+{re_bonus})")

    signal_hits = sum(1 for phrase in SIGNAL_PHRASES if phrase in text)
    sig_bonus = min(signal_hits * 6, 24)
    if sig_bonus > 0:
        score += sig_bonus
        reasons.append(f"{signal_hits} intent signals (+{sig_bonus})")

    budget = extract_budget(item.get("raw_text", ""))
    if budget != "Unknown":
        score += 8
        reasons.append("budget mentioned (+8)")

    # Bonus if real name was extracted from URL
    name = item.get("name", "")
    if name and "Profile" not in name and "Page" not in name and "Contact" not in name:
        score += 5
        reasons.append("real name found (+5)")

    query_words = [w for w in query.lower().split() if len(w) > 3]
    q_hits = sum(1 for w in query_words if w in text)
    q_bonus = min(q_hits * 3, 12)
    if q_bonus > 0:
        score += q_bonus

    score = min(score, 100)
    reason = ", ".join(reasons[:3]) if reasons else "General match"
    return score, reason


def get_recommended_approach(item: dict, score: int) -> str:
    itype = item.get("investor_type", "Investor")
    interest = item.get("interest", "Dubai property")
    platform = item.get("platform", "web")
    source_label = PLATFORM_SOURCE_MAP.get(platform, platform)

    if score >= 85:
        return f"High priority — connect on {source_label} and reference their {interest} interest directly"
    elif score >= 70:
        return f"Send personalized message about {interest} opportunities matching their profile"
    else:
        return f"Add to nurture list — share relevant {interest} market updates via {source_label}"


async def run_qualification(
    extracted_leads: List[dict],
    original_query: str,
    max_leads: int = 20
) -> List[QualifiedLead]:
    print(f"[Qualification] Scoring {len(extracted_leads)} leads (free mode v4)")
    qualified = []

    for item in extracted_leads:
        score, reason = score_lead(item, original_query)
        if score < 25:
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
            print(f"[Qualification] Skipping: {e}")
            continue

    qualified.sort(key=lambda x: x.score, reverse=True)
    print(f"[Qualification] {len(qualified)} leads qualified")
    return qualified[:max_leads]
