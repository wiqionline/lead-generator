"""
Events Scraper Agent
─────────────────────
Scrapes webinars, seminars, exhibitions, and expos
for real estate investor signals.

Free sources:
- Eventbrite (public events)
- Meetup (public groups)
- Dubai Calendar / Visit Dubai events
- GITEX, Cityscape, Arabian Travel Market attendee signals
- Google snippets for event attendees/speakers
- YouTube webinar comments
- Eventbrite + Lu.ma + Hopin public pages
"""
import httpx
import asyncio
import re
from bs4 import BeautifulSoup
from typing import List
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Major Dubai/UAE real estate events to target ──────────
DUBAI_RE_EVENTS = [
    # Cityscape — biggest RE expo in MENA
    "Cityscape Dubai",
    "Cityscape Global",
    # Property-specific
    "Dubai Property Show",
    "UAE Property Expo",
    "Off Plan Property Show Dubai",
    "Dubai Real Estate Forum",
    "Arabian Property Show",
    # Investment focused
    "Dubai Investment Week",
    "UAE Investment Summit",
    "Gulf Investment Forum",
    "MENA Real Estate Forum",
    # Large expos with RE sections
    "GITEX Dubai property investment",
    "Arabian Travel Market investment",
    "Dubai Expo real estate investor",
    "INDEX Dubai property",
    # Webinar focused
    "Dubai property webinar investors",
    "off-plan investment webinar Dubai",
    "UAE real estate seminar investors 2024",
    "Dubai property masterclass investor",
]

# ── Direct event platform URLs to scrape ──────────────────
EVENTBRITE_SEARCHES = [
    "https://www.eventbrite.com/d/united-arab-emirates--dubai/real-estate/",
    "https://www.eventbrite.com/d/united-arab-emirates--dubai/property-investment/",
    "https://www.eventbrite.com/d/online/dubai-real-estate/",
    "https://www.eventbrite.com/d/united-arab-emirates--dubai/off-plan/",
]

MEETUP_SEARCHES = [
    "https://www.meetup.com/find/?keywords=real+estate+dubai&source=EVENTS",
    "https://www.meetup.com/find/?keywords=property+investment+dubai&source=EVENTS",
    "https://www.meetup.com/find/?keywords=dubai+investors&source=GROUPS",
]

INVESTMENT_KEYWORDS = [
    "investor", "investment", "invest", "off-plan", "property",
    "real estate", "portfolio", "capital", "fund", "buyer",
    "purchasing", "ROI", "yield", "developer", "hnwi",
    "family office", "wealth", "asset", "acquisition"
]

ATTENDEE_SIGNALS = [
    "attending", "attended", "speaker", "panelist", "exhibitor",
    "registered", "attendee", "delegate", "participant",
    "booth", "stand", "networking", "connect", "met at",
    "saw at", "presented at", "joining", "will attend"
]


async def ddg_search(query: str, max_results: int = 8) -> List[dict]:
    """Free DuckDuckGo search."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "us-en"}
            )
            soup = BeautifulSoup(resp.text, "lxml")
            for r in soup.select(".result")[:max_results]:
                title = r.select_one(".result__title")
                snippet = r.select_one(".result__snippet")
                url = r.select_one(".result__url")
                if title and snippet:
                    results.append({
                        "title": title.get_text(strip=True),
                        "snippet": snippet.get_text(strip=True),
                        "url": url.get_text(strip=True) if url else "",
                    })
    except Exception as e:
        print(f"[Events] DDG error: {e}")
    return results


async def scrape_url(url: str) -> str:
    """Fetch a page and return its text."""
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                # Remove script/style noise
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception:
        pass
    return ""


def has_investor_signal(text: str) -> bool:
    text_lower = text.lower()
    has_invest = any(kw in text_lower for kw in INVESTMENT_KEYWORDS)
    has_attend = any(sig in text_lower for sig in ATTENDEE_SIGNALS)
    return has_invest or has_attend


def extract_event_name(text: str, title: str) -> str:
    """Try to extract event name from text."""
    event_patterns = [
        r"(?:at|attending|attended|joining)\s+([A-Z][A-Za-z\s&]+(?:Summit|Forum|Expo|Show|Conference|Seminar|Webinar|Event|Exhibition|Masterclass))",
        r"([A-Z][A-Za-z\s&]+(?:Summit|Forum|Expo|Show|Conference|Seminar|Webinar|Exhibition))",
    ]
    for pattern in event_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return title[:60] if title else "Event"


# ══════════════════════════════════════════════════════════
# SCRAPER 1 — Google snippets for event attendees
# ══════════════════════════════════════════════════════════

async def scrape_event_google_snippets(user_query: str) -> List[RawLead]:
    """Search Google for investor signals at specific events."""
    leads = []
    seen_urls = set()

    # Build event-specific queries
    queries = []
    for event in DUBAI_RE_EVENTS[:8]:
        queries.append(f'"{event}" investor attendee 2024 OR 2025')
        queries.append(f'site:linkedin.com "{event}" investor Dubai property')

    # Also add user query context
    queries.extend([
        f'{user_query} webinar attendee Dubai real estate',
        f'{user_query} seminar speaker Dubai property investor',
        f'{user_query} expo exhibition Dubai investor 2024 OR 2025',
        f'Cityscape Dubai {user_query} investor',
        f'"Dubai Property Show" {user_query} investor attending',
    ])

    for query in queries[:10]:  # Limit to control rate
        try:
            results = await ddg_search(query, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                if not has_investor_signal(combined):
                    continue

                event_name = extract_event_name(combined, r["title"])

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url="https://" + url if url and not url.startswith("http") else url,
                    raw_text=f"[EVENT: {event_name}] {combined[:500]}",
                    platform="event_google"
                ))

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"[Events] Google snippet error: {e}")

    print(f"[Events] Google snippets: {len(leads)} event signals")
    return leads


# ══════════════════════════════════════════════════════════
# SCRAPER 2 — Eventbrite direct scrape
# ══════════════════════════════════════════════════════════

async def scrape_eventbrite(user_query: str) -> List[RawLead]:
    """Scrape Eventbrite for Dubai RE investment events."""
    leads = []

    # Search Eventbrite via DuckDuckGo (more reliable than direct scrape)
    queries = [
        f'site:eventbrite.com Dubai real estate investment {user_query}',
        f'site:eventbrite.com Dubai property investor seminar webinar',
        f'site:eventbrite.com UAE off-plan property investment event',
        f'site:eventbrite.com Dubai investor networking property 2024 OR 2025',
    ]

    seen = set()
    for query in queries:
        try:
            results = await ddg_search(query, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url in seen:
                    continue
                seen.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                if not has_investor_signal(combined):
                    continue

                # Try to fetch the actual Eventbrite page for more details
                full_url = "https://" + url if not url.startswith("http") else url
                page_text = ""
                if "eventbrite.com" in url:
                    page_text = await scrape_url(full_url)
                    await asyncio.sleep(0.5)

                raw = f"[EVENTBRITE] {combined} {page_text[:300]}"

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url=full_url,
                    raw_text=raw[:600],
                    platform="eventbrite"
                ))

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"[Events] Eventbrite error: {e}")

    print(f"[Events] Eventbrite: {len(leads)} signals")
    return leads


# ══════════════════════════════════════════════════════════
# SCRAPER 3 — Meetup groups
# ══════════════════════════════════════════════════════════

async def scrape_meetup(user_query: str) -> List[RawLead]:
    """Search Meetup for Dubai RE investor groups."""
    leads = []

    queries = [
        f'site:meetup.com Dubai real estate investors group',
        f'site:meetup.com Dubai property investment networking',
        f'site:meetup.com UAE investors property group {user_query}',
    ]

    seen = set()
    for query in queries:
        try:
            results = await ddg_search(query, max_results=4)
            for r in results:
                url = r.get("url", "")
                if url in seen:
                    continue
                seen.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                if not has_investor_signal(combined):
                    continue

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url="https://" + url if not url.startswith("http") else url,
                    raw_text=f"[MEETUP] {combined[:500]}",
                    platform="meetup"
                ))

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"[Events] Meetup error: {e}")

    print(f"[Events] Meetup: {len(leads)} signals")
    return leads


# ══════════════════════════════════════════════════════════
# SCRAPER 4 — YouTube webinar comments & descriptions
# ══════════════════════════════════════════════════════════

async def scrape_youtube_webinars(user_query: str) -> List[RawLead]:
    """Find investor signals in YouTube webinar descriptions."""
    leads = []

    queries = [
        f'site:youtube.com Dubai real estate webinar investor {user_query} 2024 OR 2025',
        f'site:youtube.com off-plan Dubai property seminar investors',
        f'site:youtube.com Cityscape Dubai investor seminar',
        f'site:youtube.com "Dubai property" investment masterclass attendees',
    ]

    seen = set()
    for query in queries[:3]:
        try:
            results = await ddg_search(query, max_results=4)
            for r in results:
                url = r.get("url", "")
                if url in seen:
                    continue
                seen.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                if not has_investor_signal(combined):
                    continue

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url="https://" + url if not url.startswith("http") else url,
                    raw_text=f"[YOUTUBE WEBINAR] {combined[:500]}",
                    platform="youtube_webinar"
                ))

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"[Events] YouTube error: {e}")

    print(f"[Events] YouTube webinars: {len(leads)} signals")
    return leads


# ══════════════════════════════════════════════════════════
# SCRAPER 5 — Cityscape & major expo specific signals
# ══════════════════════════════════════════════════════════

async def scrape_major_expos(user_query: str) -> List[RawLead]:
    """Target signals from Cityscape, Gulf Investment Forum, etc."""
    leads = []

    expo_queries = [
        f'Cityscape Dubai 2024 OR 2025 investor exhibitor attendee {user_query}',
        f'"Gulf Investment Forum" Dubai property investor 2024 OR 2025',
        f'"Dubai Property Show" investor buyer attendee off-plan',
        f'"Arabian Property Show" investor Dubai buyer 2024 OR 2025',
        f'"Dubai Real Estate Forum" speaker investor attendee',
        f'MIPIM Dubai investor real estate {user_query}',
        f'"Index Dubai" property investor design 2024 OR 2025',
    ]

    seen = set()
    for query in expo_queries[:6]:
        try:
            results = await ddg_search(query, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url in seen:
                    continue
                seen.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                if not has_investor_signal(combined):
                    continue

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url="https://" + url if not url.startswith("http") else url,
                    raw_text=f"[EXPO/EXHIBITION] {combined[:500]}",
                    platform="expo"
                ))

            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"[Events] Expo error: {e}")

    print(f"[Events] Major expos: {len(leads)} signals")
    return leads


# ══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════

async def run_events_scraper(user_query: str) -> List[RawLead]:
    """
    Main events scraper — runs all 5 sub-scrapers concurrently.
    Covers: Google snippets, Eventbrite, Meetup, YouTube, Major Expos.
    """
    print(f"[Events] Starting events scraper for: {user_query}")

    results = await asyncio.gather(
        scrape_event_google_snippets(user_query),
        scrape_eventbrite(user_query),
        scrape_meetup(user_query),
        scrape_youtube_webinars(user_query),
        scrape_major_expos(user_query),
        return_exceptions=True
    )

    all_leads: List[RawLead] = []
    source_names = ["google_snippets", "eventbrite", "meetup", "youtube", "expos"]

    for i, result in enumerate(results):
        if isinstance(result, list):
            all_leads.extend(result)
        elif isinstance(result, Exception):
            print(f"[Events] {source_names[i]} failed: {result}")

    # Deduplicate by URL
    seen = set()
    unique = []
    for lead in all_leads:
        key = lead.source_url or lead.raw_text[:60]
        if key not in seen:
            seen.add(key)
            unique.append(lead)

    print(f"[Events] Total unique event signals: {len(unique)}")
    return unique
