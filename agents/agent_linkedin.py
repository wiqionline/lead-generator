"""
AGENT 2 — LinkedIn Intent Scraper
───────────────────────────────────
Specific task: Find LinkedIn profiles of people who have
PUBLICLY signalled Dubai property investment intent.

Looks for:
- People who posted about buying/investing in Dubai
- People who commented on Dubai property posts
- People whose headline/about mentions Dubai RE investment
- Recent LinkedIn articles about Dubai property investment

Output: Real names + LinkedIn URLs + intent signals
"""
import httpx
import asyncio
import re
from bs4 import BeautifulSoup
from typing import List
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# High-intent LinkedIn search queries
LINKEDIN_QUERIES = [
    # People posting about buying
    'site:linkedin.com "looking to invest" OR "want to buy" Dubai property',
    'site:linkedin.com "off-plan" Dubai "investor" "AED" OR "million" 2024 OR 2025',
    'site:linkedin.com "Dubai real estate" "investment" "portfolio" buyer 2024',
    # People with investor profiles
    'site:linkedin.com/in "real estate investor" Dubai "AED" OR "portfolio"',
    'site:linkedin.com/in "property investor" Dubai UAE "off-plan"',
    'site:linkedin.com/in "HNWI" OR "family office" Dubai property investment',
    # People asking questions = genuine seekers
    'site:linkedin.com Dubai property "which developer" OR "best area" OR "good ROI" investor',
    'site:linkedin.com "investing in Dubai" "first time" OR "looking for" property 2024',
]

INTENT_PHRASES = [
    "looking to invest", "want to buy", "buying property",
    "investment portfolio", "off-plan", "seeking opportunities",
    "expanding portfolio", "real estate investor", "property investor",
    "hnwi", "family office", "high net worth",
]


def extract_name_from_linkedin_url(url: str) -> str:
    """Extract real name from LinkedIn profile URL."""
    match = re.search(r"linkedin\.com/in/([a-z0-9\-]+)", url, re.IGNORECASE)
    if match:
        slug = match.group(1)
        slug = re.sub(r"-?\d+$", "", slug).strip("-")
        parts = [p for p in slug.split("-") if len(p) > 1]
        if parts:
            return " ".join(p.capitalize() for p in parts[:3])
    return ""


async def ddg_search(query: str, max_results: int = 8) -> List[dict]:
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
                url_el = r.select_one(".result__url")
                if title and snippet:
                    results.append({
                        "title": title.get_text(strip=True),
                        "snippet": snippet.get_text(strip=True),
                        "url": url_el.get_text(strip=True) if url_el else "",
                    })
    except Exception as e:
        print(f"[LinkedIn] Search error: {e}")
    return results


async def run_linkedin_agent(user_query: str) -> List[RawLead]:
    """
    AGENT 2 — Find LinkedIn profiles with real investment intent.
    Only returns profiles where intent signal is found in snippet.
    """
    print(f"[Agent2:LinkedIn] Searching for investor profiles...")
    leads = []
    seen_urls = set()

    # Add user query context to searches
    custom_queries = [
        f'site:linkedin.com/in {user_query} Dubai property investor',
        f'site:linkedin.com {user_query} "Dubai" "invest" "property" 2024',
    ]

    all_queries = LINKEDIN_QUERIES + custom_queries

    for query in all_queries[:8]:
        try:
            results = await ddg_search(query, max_results=6)
            for r in results:
                url = r.get("url", "")
                if url in seen_urls:
                    continue
                if "linkedin.com" not in url:
                    continue
                seen_urls.add(url)

                combined = f"{r['title']} | {r['snippet']}"
                combined_lower = combined.lower()

                # Must have investment intent
                has_intent = any(p in combined_lower for p in INTENT_PHRASES)
                # Must NOT be an agent/broker page
                is_agent = any(w in combined_lower for w in [
                    "real estate agent", "property consultant",
                    "we offer", "our properties", "listing"
                ])

                if not has_intent or is_agent:
                    continue

                # Try to get real name from URL
                full_url = "https://" + url if not url.startswith("http") else url
                name = extract_name_from_linkedin_url(full_url) or r["title"].split("|")[0].strip()

                leads.append(RawLead(
                    name=name,
                    source_url=full_url,
                    raw_text=f"[LINKEDIN INVESTOR] {combined[:500]}",
                    platform="linkedin"
                ))

            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"[Agent2:LinkedIn] Query error: {e}")

    print(f"[Agent2:LinkedIn] Found {len(leads)} investor profiles")
    return leads
