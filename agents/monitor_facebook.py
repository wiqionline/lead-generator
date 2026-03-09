"""
Facebook Group Monitor — email/password login
Fixed for current mbasic.facebook.com structure
"""
import httpx
import asyncio
import re
import os
from bs4 import BeautifulSoup
from typing import List, Optional
from core.models import RawLead

FB_GROUPS = [
    "dubaipropertyinvestors",
    "DubaiRealEstateInvestors",
    "UAEPropertyInvestment",
    "DubaiPropertyBuyers",
    "OffPlanDubaiGroup",
]

BUYER_INTENT = [
    "looking for", "looking to buy", "want to buy", "want to invest",
    "planning to buy", "interested in buying", "searching for",
    "need advice", "recommend", "which area", "best area",
    "good roi", "payment plan", "off plan", "budget",
    "can anyone", "anyone know", "help me find",
    "which developer", "is it worth", "aed", "million",
    "2m", "3m", "5m", "first time buyer",
]

SPAM = [
    "we offer", "we have exclusive", "book now",
    "register now", "limited units", "special price",
    "launch price", "for sale:", "sqft", "1br from",
]

PHONE_RE = re.compile(r"(\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}|05\d[\s\-]?\d{3}[\s\-]?\d{4})")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def is_buyer(text: str) -> bool:
    tl = text.lower()
    return (
        any(p in tl for p in BUYER_INTENT) and
        sum(1 for s in SPAM if s in tl) < 2
    )


async def login_facebook(email: str, password: str) -> Optional[httpx.AsyncClient]:
    """Login using mbasic Facebook."""
    try:
        client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20)

        # Get login page
        resp = await client.get("https://mbasic.facebook.com/")
        soup = BeautifulSoup(resp.text, "lxml")

        # Find login form — try multiple selectors
        form = (
            soup.select_one('form[action*="login"]') or
            soup.select_one('form[method="post"]') or
            soup.select_one("form")
        )

        if not form:
            print("[Facebook] No login form found — trying direct POST")
            # Try direct login POST
            resp2 = await client.post(
                "https://mbasic.facebook.com/login/device-based/regular/login/?refsrc=deprecated",
                data={
                    "email": email,
                    "pass": password,
                    "login": "Log In",
                }
            )
            if "c_user" in resp2.headers.get("set-cookie", "") or "home" in str(resp2.url):
                print("[Facebook] Direct login successful")
                return client
            return None

        # Collect form fields
        data = {}
        for inp in form.select("input[name]"):
            data[inp.get("name")] = inp.get("value", "")
        data["email"] = email
        data["pass"] = password

        action = form.get("action", "/login/device-based/regular/login/")
        if action.startswith("/"):
            action = "https://mbasic.facebook.com" + action

        resp2 = await client.post(action, data=data)
        page = resp2.text.lower()

        if any(x in page for x in ["logout", "your feed", "news feed", "c_user"]):
            print("[Facebook] Login successful")
            return client
        elif "checkpoint" in str(resp2.url) or "checkpoint" in page:
            print("[Facebook] Login blocked by checkpoint — Facebook security check")
            return None
        elif "two_step" in page or "two-factor" in page:
            print("[Facebook] 2FA required")
            return None
        else:
            print("[Facebook] Login status unclear — attempting to continue")
            return client

    except Exception as e:
        print(f"[Facebook] Login error: {e}")
        return None


async def scrape_group(client: httpx.AsyncClient, group_id: str) -> List[RawLead]:
    leads = []
    try:
        url = f"https://mbasic.facebook.com/groups/{group_id}"
        resp = await client.get(url)

        if "login" in str(resp.url).lower():
            return leads

        soup = BeautifulSoup(resp.text, "lxml")

        # Get all text blocks
        all_text_blocks = []

        # Try structured posts first
        for sel in ["div[data-ft]", "article", ".story_body_container"]:
            blocks = soup.select(sel)
            if blocks:
                all_text_blocks = blocks
                break

        # Fallback to paragraphs
        if not all_text_blocks:
            all_text_blocks = soup.select("p, div.t, span")

        for block in all_text_blocks[:30]:
            text = block.get_text(separator=" ", strip=True)
            if len(text) < 30 or not is_buyer(text):
                continue

            author = "Facebook User"
            for sel in ["h3 a", "strong a", "h3", "strong"]:
                el = block.select_one(sel)
                if el:
                    candidate = el.get_text(strip=True)
                    if 2 < len(candidate) < 60:
                        author = candidate
                        break

            phone = None
            m = PHONE_RE.search(text)
            if m:
                phone = re.sub(r"[\s\-]", "", m.group())

            post_link = f"https://www.facebook.com/groups/{group_id}"
            for a in block.select("a[href]"):
                href = a.get("href", "")
                if "/permalink/" in href or "/posts/" in href:
                    post_link = "https://www.facebook.com" + href if href.startswith("/") else href
                    break

            leads.append(RawLead(
                name=author,
                source_url=post_link,
                raw_text=f"[FACEBOOK: {group_id}]\nAuthor: {author}\nPhone: {phone or 'not shared'}\nPost: {text[:400]}",
                platform="facebook_group"
            ))

    except Exception as e:
        print(f"[Facebook] Scrape error {group_id}: {e}")
    return leads


async def run_facebook_monitor(user_query: str) -> List[RawLead]:
    email = os.getenv("FB_EMAIL")
    password = os.getenv("FB_PASSWORD")

    if not email or not password:
        print("[Facebook] No credentials — skipping")
        return []

    print(f"[Facebook] Logging in as {email}...")
    client = await login_facebook(email, password)

    if not client:
        print("[Facebook] Login failed")
        return []

    all_leads = []
    for group_id in FB_GROUPS:
        print(f"[Facebook] Scanning: {group_id}")
        leads = await scrape_group(client, group_id)
        all_leads.extend(leads)
        print(f"[Facebook] {group_id}: {len(leads)} buyer signals")
        await asyncio.sleep(3)

    await client.aclose()
    print(f"[Facebook] Total: {len(all_leads)} signals")
    return all_leads
