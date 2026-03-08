"""
PropertyFinder Scraper Agent
─────────────────────────────
Scrapes PropertyFinder.ae for investor signals:
- Off-plan listings with developer info
- Investment property categories
- Agent profiles with multiple listings
Free — PropertyFinder is a public website.
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

PF_URLS = [
    "https://www.propertyfinder.ae/en/buy/apartments-for-sale-in-dubai.html",
    "https://www.propertyfinder.ae/en/new-projects/dubai.html",
    "https://www.propertyfinder.ae/en/buy/apartments-for-sale-in-downtown-dubai.html",
    "https://www.propertyfinder.ae/en/buy/apartments-for-sale-in-dubai-marina.html",
    "https://www.propertyfinder.ae/en/buy/apartments-for-sale-in-palm-jumeirah.html",
]

INVESTMENT_KEYWORDS = [
    "investor", "investment", "off-plan", "developer", "ROI",
    "return", "yield", "portfolio", "handover", "payment plan",
    "launching", "pre-launch", "off plan", "capital appreciation"
]

async def scrape_pf_page(url: str, client: httpx.AsyncClient) -> List[RawLead]:
    leads = []
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            print(f"[PropertyFinder] Status {resp.status_code} for {url}")
            return leads

        soup = BeautifulSoup(resp.text, "lxml")

        # PropertyFinder uses card-based listings
        listings = (
            soup.select("[class*='card']") or
            soup.select("[class*='listing']") or
            soup.select("article") or
            soup.select("[data-testid*='property']")
        )

        for item in listings[:12]:
            text = item.get_text(separator=" ", strip=True)
            if len(text) < 40:
                continue
            if not any(kw.lower() in text.lower() for kw in INVESTMENT_KEYWORDS):
                continue

            # Try to extract agent/developer name
            name = "PropertyFinder Agent/Developer"
            for sel in ["[class*='agent']", "[class*='developer']", "[class*='broker']"]:
                el = item.select_one(sel)
                if el:
                    candidate = el.get_text(strip=True)
                    if len(candidate) > 2:
                        name = candidate
                        break

            link = ""
            a = item.select_one("a[href]")
            if a:
                href = a.get("href", "")
                link = f"https://www.propertyfinder.ae{href}" if href.startswith("/") else href

            leads.append(RawLead(
                name=name,
                source_url=link or url,
                raw_text=text[:600],
                platform="propertyfinder"
            ))

        # Fallback to page text
        if not leads:
            page_text = soup.get_text(separator=" ", strip=True)
            if any(kw.lower() in page_text.lower() for kw in INVESTMENT_KEYWORDS):
                leads.append(RawLead(
                    name="PropertyFinder Page",
                    source_url=url,
                    raw_text=page_text[:800],
                    platform="propertyfinder"
                ))
    except Exception as e:
        print(f"[PropertyFinder] Error on {url}: {e}")
    return leads


async def run_propertyfinder_scraper(user_query: str) -> List[RawLead]:
    print(f"[PropertyFinder] Scraping for: {user_query}")
    all_leads: List[RawLead] = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [scrape_pf_page(url, client) for url in PF_URLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)

    print(f"[PropertyFinder] {len(all_leads)} signals found")
    return all_leads
