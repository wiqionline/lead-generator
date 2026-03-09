"""
Google Snippets Multi-Platform Scraper
────────────────────────────────────────
Uses DuckDuckGo (free, no API key) to surface investor signals
from LinkedIn, Facebook, Instagram, Dubizzle, Reddit, Twitter/X,
YouTube, forums, and news — all via search snippets.

This is the backbone of the discovery layer.
No logins, no blocked scrapers, no API keys needed.
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List, Dict
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Platform-specific query templates ─────────────────────
# {query} is replaced with the user's search intent

PLATFORM_QUERIES: Dict[str, List[str]] = {

    "linkedin": [
        "site:linkedin.com/in {query} investor Dubai real estate",
        "site:linkedin.com/in {query} off-plan property UAE",
        "site:linkedin.com/company {query} real estate investment Dubai",
        "site:linkedin.com {query} \"looking to invest\" OR \"interested in\" Dubai property",
    ],

    "facebook": [
        "site:facebook.com {query} Dubai property investor group",
        "site:facebook.com/groups {query} real estate investors UAE",
        "site:facebook.com {query} \"off-plan\" OR \"investment\" Dubai 2024 OR 2025",
        "site:facebook.com {query} buy property Dubai interested",
    ],

    "instagram": [
        "site:instagram.com {query} Dubai real estate investor",
        "site:instagram.com {query} property investment UAE",
        "instagram.com {query} \"#dubaipropertyinvestment\" OR \"#dubairealestate\"",
    ],

    "dubizzle": [
        "site:dubizzle.com {query} investor property Dubai",
        "site:dubizzle.com/dubai {query} off-plan investment",
        "dubizzle.com Dubai property investment {query}",
    ],

    "reddit": [
        "site:reddit.com {query} Dubai real estate invest",
        "site:reddit.com/r/dubai {query} property investment advice",
        "site:reddit.com {query} \"buying property\" Dubai investor",
    ],

    "twitter_x": [
        "site:twitter.com {query} Dubai property investment 2024 OR 2025",
        "site:x.com {query} investing Dubai real estate off-plan",
        "twitter.com {query} \"interested in Dubai\" property investor",
    ],

    "youtube": [
        "site:youtube.com {query} Dubai real estate investment strategy 2024",
        "site:youtube.com {query} off-plan property Dubai investor guide",
    ],

    "forums_news": [
        "{query} Dubai real estate investor forum 2024 OR 2025",
        "{query} off-plan Dubai property \"looking for\" OR \"seeking\" investor",
        "{query} UAE property investor news announcement",
        "{query} Dubai HNWI family office real estate investment",
        "{query} GCC investor Dubai property portfolio",
        "\"{query}\" real estate investor Dubai contact",
    ],
}


async def ddg_search(query: str, max_results: int = 8) -> List[Dict]:
    """DuckDuckGo HTML search — free, no API key, no rate limit enforced."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "us-en"}
            )
            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result")[:max_results]:
                title_el = result.select_one(".result__title")
                snippet_el = result.select_one(".result__snippet")
                url_el = result.select_one(".result__url")
                if title_el and snippet_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "snippet": snippet_el.get_text(strip=True),
                        "url": url_el.get_text(strip=True) if url_el else "",
                        "query": query
                    })
    except Exception as e:
        print(f"[GoogleSnippets] Search error for '{query[:50]}': {e}")
    return results


def result_to_raw_lead(result: Dict, platform: str) -> RawLead:
    """Convert a search result dict to a RawLead."""
    raw_text = f"{result['title']} | {result['snippet']}"
    url = result["url"]
    if url and not url.startswith("http"):
        url = "https://" + url

    # Try to extract a name hint from title
    title = result["title"]
    name_parts = []
    for word in title.split()[:4]:
        if word and word[0].isupper() and len(word) > 1 and word.isalpha():
            name_parts.append(word)
        if len(name_parts) == 2:
            break

    name = " ".join(name_parts) if name_parts else f"{platform.title()} Profile"

    return RawLead(
        name=name,
        source_url=url,
        raw_text=raw_text[:600],
        platform=platform
    )


async def run_platform_searches(user_query: str, platforms: List[str] = None) -> List[RawLead]:
    """
    Run DuckDuckGo searches across all platforms for a given query.
    Returns deduplicated RawLead list.
    """
    if platforms is None:
        platforms = list(PLATFORM_QUERIES.keys())

    print(f"[GoogleSnippets] Searching {len(platforms)} platforms for: {user_query}")
    all_leads: List[RawLead] = []
    seen_urls = set()

    for platform in platforms:
        queries = PLATFORM_QUERIES.get(platform, [])
        platform_leads = []

        for query_template in queries[:2]:  # Max 2 queries per platform to stay fast
            query = query_template.replace("{query}", user_query)
            results = await ddg_search(query, max_results=5)

            for result in results:
                url = result.get("url", "")
                if url and url in seen_urls:
                    continue
                seen_urls.add(url)

                if len(result.get("snippet", "")) > 30:
                    lead = result_to_raw_lead(result, platform)
                    platform_leads.append(lead)

            await asyncio.sleep(1.2)  # Respect rate limits between searches

        print(f"[GoogleSnippets] {platform}: {len(platform_leads)} results")
        all_leads.extend(platform_leads)

    print(f"[GoogleSnippets] Total: {len(all_leads)} signals across all platforms")
    return all_leads


async def run_google_snippets_scraper(user_query: str) -> List[RawLead]:
    """Main entry point for the Google Snippets scraper."""
    return await run_platform_searches(user_query)

# ── Add events/webinar queries to existing platform map ───
PLATFORM_QUERIES["webinars"] = [
    "site:eventbrite.com {query} Dubai property investor",
    "site:meetup.com {query} Dubai real estate investors",
    "{query} Dubai property webinar seminar attendee investor 2024 OR 2025",
    "{query} Cityscape Dubai investor OR exhibitor OR attendee",
]

PLATFORM_QUERIES["seminars_expos"] = [
    "{query} \"Dubai Property Show\" OR \"Cityscape\" investor attendee",
    "{query} real estate expo exhibition Dubai investor speaker",
    "{query} \"Gulf Investment Forum\" OR \"MENA Real Estate\" investor 2024",
    "site:linkedin.com {query} attended Cityscape Dubai investor",
]
