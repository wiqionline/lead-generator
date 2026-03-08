"""
Bayut Scraper Agent
────────────────────
Scrapes Bayut.com for investor signals:
- Off-plan project listings with developer/agent info
- Investment-tagged properties
- Developer company names and contacts
Free — Bayut is a fully public website.
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

BAYUT_URLS = [
    "https://www.bayut.com/to-buy/property/dubai/?purpose=for-sale",
    "https://www.bayut.com/to-buy/apartments/dubai/downtown-dubai/",
    "https://www.bayut.com/to-buy/apartments/dubai/dubai-marina/",
    "https://www.bayut.com/to-buy/apartments/dubai/palm-jumeirah/",
    "https://www.bayut.com/to-buy/apartments/dubai/business-bay/",
]

INVESTMENT_KEYWORDS = [
    "investor", "investment", "off-plan", "off plan", "developer",
    "ROI", "return", "yield", "capital", "portfolio", "handover",
    "payment plan", "launching", "pre-launch"
]

async def scrape_page(url: str, client: httpx.AsyncClient) -> List[RawLead]:
    leads = []
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            return leads
        soup = BeautifulSoup(resp.text, "lxml")

        # Try multiple selectors Bayut uses
        listings = (
            soup.select("article") or
            soup.select("[class*='listing']") or
            soup.select("[class*='property-card']")
        )

        for item in listings[:12]:
            text = item.get_text(separator=" ", strip=True)
            if len(text) < 40:
                continue
            if not any(kw.lower() in text.lower() for kw in INVESTMENT_KEYWORDS):
                continue

            # Try to get agent/developer name
            name = "Bayut Agent/Developer"
            for sel in ["[class*='agent-name']", "[class*='developer']", "span[class*='name']"]:
                el = item.select_one(sel)
                if el:
                    name = el.get_text(strip=True)
                    break

            link = ""
            a = item.select_one("a[href]")
            if a:
                href = a.get("href", "")
                link = f"https://www.bayut.com{href}" if href.startswith("/") else href

            leads.append(RawLead(
                name=name,
                source_url=link or url,
                raw_text=text[:600],
                platform="bayut"
            ))

        # Fallback: full page text if no structured listings found
        if not leads:
            page_text = soup.get_text(separator=" ", strip=True)
            if any(kw.lower() in page_text.lower() for kw in INVESTMENT_KEYWORDS):
                leads.append(RawLead(
                    name="Bayut Page",
                    source_url=url,
                    raw_text=page_text[:800],
                    platform="bayut"
                ))
    except Exception as e:
        print(f"[Bayut] Error on {url}: {e}")
    return leads


async def run_bayut_scraper(user_query: str) -> List[RawLead]:
    print(f"[Bayut] Scraping for: {user_query}")
    all_leads: List[RawLead] = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [scrape_page(url, client) for url in BAYUT_URLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)
        await asyncio.sleep(1)

        # Keyword search on Bayut
        search_url = f"https://www.bayut.com/to-buy/property/dubai/?q={user_query.replace(' ', '+')}"
        kw_leads = await scrape_page(search_url, client)
        all_leads.extend(kw_leads)

    print(f"[Bayut] {len(all_leads)} signals found")
    return all_leads
