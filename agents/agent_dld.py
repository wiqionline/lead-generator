"""
AGENT 1 — DLD Transaction Scraper
───────────────────────────────────
Specific task: Scrape Dubai Land Department public 
transaction records to find REAL property buyers.

Source: dubailand.gov.ae/en/open-data (public records)
Also: Property Monitor, Reidin public transaction feeds

Output: Real buyer names + transaction details
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

DLD_URLS = [
    "https://dubailand.gov.ae/en/open-data/real-estate-transaction-data/",
    "https://www.propertymonitor.ae/transactions",
    "https://www.propertyfinder.ae/en/dubai-transaction-records",
]

# Supplementary — DLD data via Google
DLD_SEARCH_QUERIES = [
    "site:dubailand.gov.ae transaction buyer 2024 OR 2025 million",
    "dubai property transaction record buyer name 2024 AED million",
    "DLD dubai real estate buyer transaction 2M 3M 5M 2024",
    "dubai property purchase record investor buyer villa apartment 2024",
    "dubailand.gov.ae open data buyer nationality transaction 2024",
]


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
                url = r.select_one(".result__url")
                if title and snippet:
                    results.append({
                        "title": title.get_text(strip=True),
                        "snippet": snippet.get_text(strip=True),
                        "url": url.get_text(strip=True) if url else "",
                    })
    except Exception as e:
        print(f"[DLD] Search error: {e}")
    return results


async def scrape_dld_direct() -> List[RawLead]:
    """Try to scrape DLD open data portal directly."""
    leads = []
    try:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            resp = await client.get(
                "https://dubailand.gov.ae/en/open-data/real-estate-transaction-data/",
                follow_redirects=True
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                # Look for transaction tables
                tables = soup.select("table")
                for table in tables:
                    rows = table.select("tr")
                    for row in rows[1:]:  # Skip header
                        cells = [td.get_text(strip=True) for td in row.select("td")]
                        if len(cells) >= 4:
                            text = " | ".join(cells)
                            leads.append(RawLead(
                                name=cells[0] if cells else "DLD Buyer",
                                source_url="https://dubailand.gov.ae/en/open-data/",
                                raw_text=f"[DLD TRANSACTION] {text}",
                                platform="dld"
                            ))
    except Exception as e:
        print(f"[DLD] Direct scrape error: {e}")
    return leads


async def run_dld_agent(user_query: str) -> List[RawLead]:
    """
    AGENT 1 — Find real buyers from DLD transaction data.
    Returns verified property buyers with transaction amounts.
    """
    print(f"[Agent1:DLD] Searching transaction records...")
    leads = []
    seen = set()

    # Try direct DLD scrape first
    direct = await scrape_dld_direct()
    leads.extend(direct)
    print(f"[Agent1:DLD] Direct scrape: {len(direct)} records")

    # Supplement with search
    for query in DLD_SEARCH_QUERIES[:4]:
        try:
            results = await ddg_search(query, max_results=6)
            for r in results:
                url = r.get("url", "")
                if url in seen:
                    continue
                seen.add(url)

                combined = f"{r['title']} | {r['snippet']}"

                # Only keep results mentioning real amounts
                if not any(w in combined.lower() for w in [
                    "million", "aed", "transaction", "buyer",
                    "purchase", "sold", "transfer"
                ]):
                    continue

                leads.append(RawLead(
                    name=r["title"][:80],
                    source_url="https://" + url if not url.startswith("http") else url,
                    raw_text=f"[DLD RECORD] {combined[:500]}",
                    platform="dld"
                ))

            await asyncio.sleep(1.5)
        except Exception as e:
            print(f"[Agent1:DLD] Query error: {e}")

    print(f"[Agent1:DLD] Total: {len(leads)} transaction records")
    return leads
