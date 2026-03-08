"""
Bayut Scraper — updated URLs 2025
"""
import httpx
import asyncio
from bs4 import BeautifulSoup
from typing import List
from core.models import RawLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BAYUT_URLS = [
    "https://www.bayut.com/property/dubai/for-sale/",
    "https://www.bayut.com/property/dubai/for-sale/?category=apartment",
    "https://www.bayut.com/property/dubai/for-sale/?purpose=investment",
    "https://www.bayut.com/new-projects/dubai/",
    "https://www.bayut.com/property/downtown-dubai/for-sale/",
    "https://www.bayut.com/property/dubai-marina/for-sale/",
    "https://www.bayut.com/property/palm-jumeirah/for-sale/",
    "https://www.bayut.com/property/business-bay/for-sale/",
]

INVESTMENT_KEYWORDS = [
    "investor", "investment", "off-plan", "off plan", "developer",
    "ROI", "return", "yield", "capital", "portfolio", "handover",
    "payment plan", "launching", "pre-launch", "freehold"
]

async def scrape_page(url: str, client: httpx.AsyncClient) -> List[RawLead]:
    leads = []
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            print(f"[Bayut] Status {resp.status_code} for {url}")
            return leads

        soup = BeautifulSoup(resp.text, "lxml")
        page_text = soup.get_text(separator=" ", strip=True)

        # Check for investment keywords in page
        if not any(kw.lower() in page_text.lower() for kw in INVESTMENT_KEYWORDS):
            return leads

        # Try structured listings first
        listings = (
            soup.select("article") or
            soup.select("[class*='listing']") or
            soup.select("[class*='property']") or
            soup.select("[class*='card']")
        )

        if listings:
            for item in listings[:10]:
                text = item.get_text(separator=" ", strip=True)
                if len(text) < 40:
                    continue
                if not any(kw.lower() in text.lower() for kw in INVESTMENT_KEYWORDS):
                    continue

                name = "Bayut Agent/Developer"
                for sel in ["[class*='agent']", "[class*='developer']", "[class*='name']"]:
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
                    link = f"https://www.bayut.com{href}" if href.startswith("/") else href

                leads.append(RawLead(name=name, source_url=link or url, raw_text=text[:600], platform="bayut"))
        else:
            # Fallback: use full page text
            leads.append(RawLead(name="Bayut Page", source_url=url, raw_text=page_text[:800], platform="bayut"))

    except Exception as e:
        print(f"[Bayut] Error on {url}: {e}")
    return leads


async def run_bayut_scraper(user_query: str) -> List[RawLead]:
    print(f"[Bayut] Scraping with updated URLs")
    all_leads: List[RawLead] = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        # Run first 4 URLs concurrently
        tasks = [scrape_page(url, client) for url in BAYUT_URLS[:4]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)
        await asyncio.sleep(1)

        # Run remaining URLs
        tasks2 = [scrape_page(url, client) for url in BAYUT_URLS[4:]]
        results2 = await asyncio.gather(*tasks2, return_exceptions=True)
        for r in results2:
            if isinstance(r, list):
                all_leads.extend(r)

    print(f"[Bayut] {len(all_leads)} signals found")
    return all_leads
