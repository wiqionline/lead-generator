"""
Facebook Group Organic Intent Monitor
───────────────────────────────────────
Logs into Facebook using email/password and monitors
investment groups for real buyer intent posts.

Setup — add to Railway variables:
  FB_EMAIL    = your Facebook email
  FB_PASSWORD = your Facebook password
"""
import httpx
import asyncio
import re
import os
from bs4 import BeautifulSoup
from typing import List, Optional
from core.models import RawLead

# ── Facebook groups to monitor ─────────────────────────────
FB_GROUPS = [
    "dubaipropertyinvestors",
    "dxbproperty",
    "35002236885",
    "35208453058",
    "uaepropertyinvestors",
    "dubairealestategroup",
    "offplandubaiinvestors",
]

BUYER_INTENT = [
    "looking for", "looking to buy", "want to buy", "want to invest",
    "planning to buy", "interested in buying", "searching for",
    "need advice", "recommend", "suggestions", "which area",
    "best area", "good roi", "payment plan", "off plan",
    "budget", "can anyone", "anyone know", "help me find",
    "where to", "how to invest", "first time buyer",
    "which developer", "is it worth", "good investment",
    "aed", "million", "2m", "3m", "5m",
]

AGENT_SPAM = [
    "we offer", "we have exclusive", "contact our",
    "book now", "register now", "limited units",
    "special price", "launch price", "click here",
    "for sale:", "sqft", "1br from", "2br from",
]

PHONE_PATTERNS = [
    r"\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}",
    r"05\d[\s\-]?\d{3}[\s\-]?\d{4}",
    r"\+\d{1,3}[\s\-]?\d{8,12}",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def is_buyer_intent(text: str) -> bool:
    text_lower = text.lower()
    has_intent = any(phrase in text_lower for phrase in BUYER_INTENT)
    is_spam = sum(1 for s in AGENT_SPAM if s in text_lower) >= 2
    return has_intent and not is_spam


def extract_phone(text: str) -> Optional[str]:
    for pattern in PHONE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"[\s\-]", "", match.group())
    return None


async def login_facebook(email: str, password: str) -> Optional[httpx.AsyncClient]:
    """
    Log into Facebook using mbasic (mobile basic) site.
    Returns authenticated client session or None.
    """
    try:
        client = httpx.AsyncClient(
            headers=HEADERS,
            follow_redirects=True,
            timeout=20,
        )

        # Step 1 — Get login page
        resp = await client.get("https://mbasic.facebook.com/login/")
        soup = BeautifulSoup(resp.text, "lxml")

        # Step 2 — Find login form fields
        form = soup.select_one("form")
        if not form:
            print("[Facebook] Could not find login form")
            return None

        # Collect hidden fields
        data = {}
        for inp in form.select("input"):
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                data[name] = value

        # Add credentials
        data["email"] = email
        data["pass"] = password

        # Step 3 — Submit login
        action = form.get("action", "https://mbasic.facebook.com/login/device-based/regular/login/")
        if action.startswith("/"):
            action = "https://mbasic.facebook.com" + action

        resp2 = await client.post(action, data=data)

        # Check if logged in
        if "logout" in resp2.text.lower() or "home" in str(resp2.url):
            print("[Facebook] Login successful")
            return client
        elif "checkpoint" in str(resp2.url):
            print("[Facebook] Login checkpoint — Facebook needs verification")
            return None
        elif "two_step" in str(resp2.url) or "2fa" in str(resp2.url):
            print("[Facebook] 2FA required — disable 2FA or use cookies")
            return None
        else:
            print("[Facebook] Login may have failed — trying to continue anyway")
            return client

    except Exception as e:
        print(f"[Facebook] Login error: {e}")
        return None


async def scrape_group(client: httpx.AsyncClient, group_id: str) -> List[RawLead]:
    """Scrape a Facebook group for buyer intent posts."""
    leads = []
    try:
        url = f"https://mbasic.facebook.com/groups/{group_id}?sorting_setting=RECENT_ACTIVITY"
        resp = await client.get(url)

        if "login" in str(resp.url):
            print(f"[Facebook] Session lost for group {group_id}")
            return leads

        soup = BeautifulSoup(resp.text, "lxml")

        # Extract posts
        posts = (
            soup.select("div[data-ft]") or
            soup.select(".story_body_container") or
            soup.select("article") or
            soup.select("div[role='article']")
        )

        # Fallback — grab all paragraphs
        if not posts:
            posts = soup.select("p, div.t")

        for post in posts[:25]:
            text = post.get_text(separator=" ", strip=True)
            if len(text) < 30:
                continue
            if not is_buyer_intent(text):
                continue

            # Get author
            author = "Facebook User"
            for sel in ["h3 a", "strong a", ".actor a", "h3", "strong"]:
                el = post.select_one(sel)
                if el:
                    candidate = el.get_text(strip=True)
                    if len(candidate) > 2 and len(candidate) < 60:
                        author = candidate
                        break

            # Get post link
            post_link = f"https://www.facebook.com/groups/{group_id}"
            for a in post.select("a[href]"):
                href = a.get("href", "")
                if "/groups/" in href and "/permalink/" in href:
                    post_link = "https://www.facebook.com" + href if href.startswith("/") else href
                    break

            phone = extract_phone(text)

            raw_text = (
                f"[FACEBOOK GROUP: {group_id}]\n"
                f"Author: {author}\n"
                f"Phone: {phone or 'not shared'}\n"
                f"Post: {text[:400]}"
            )

            leads.append(RawLead(
                name=author,
                source_url=post_link,
                raw_text=raw_text,
                platform="facebook_group"
            ))

    except Exception as e:
        print(f"[Facebook] Error scraping group {group_id}: {e}")

    return leads


async def run_facebook_monitor(user_query: str) -> List[RawLead]:
    """Main Facebook monitor entry point."""
    email = os.getenv("FB_EMAIL")
    password = os.getenv("FB_PASSWORD")

    if not email or not password:
        print("[Facebook] No FB_EMAIL or FB_PASSWORD — skipping")
        print("[Facebook] Add FB_EMAIL and FB_PASSWORD to Railway variables to enable")
        return []

    print(f"[Facebook] Logging in as {email}...")
    client = await login_facebook(email, password)

    if not client:
        print("[Facebook] Login failed — skipping Facebook scrape")
        return []

    print(f"[Facebook] Scanning {len(FB_GROUPS)} groups...")
    all_leads: List[RawLead] = []

    for group_id in FB_GROUPS:
        try:
            print(f"[Facebook] Scanning group: {group_id}")
            leads = await scrape_group(client, group_id)
            all_leads.extend(leads)
            print(f"[Facebook] {group_id}: {len(leads)} buyer signals")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[Facebook] Error on {group_id}: {e}")
            continue

    await client.aclose()
    print(f"[Facebook] Total: {len(all_leads)} genuine buyer signals")
    return all_leads
