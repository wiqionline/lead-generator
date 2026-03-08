"""
Contact Finder Agent + Report Generator
─────────────────────────────────────────
100% FREE — DuckDuckGo lookups only.
v4 — finds LinkedIn, email, AND mobile phone numbers
"""
import httpx
import asyncio
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from core.models import QualifiedLead

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Phone number patterns (international) ─────────────────
PHONE_PATTERNS = [
    r"\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}",   # UAE +971 5x xxx xxxx
    r"\+44[\s\-]?\d{4}[\s\-]?\d{6}",                  # UK
    r"\+1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", # US/Canada
    r"\+91[\s\-]?\d{5}[\s\-]?\d{5}",                  # India
    r"\+966[\s\-]?\d{2}[\s\-]?\d{7}",                 # Saudi
    r"\+65[\s\-]?\d{4}[\s\-]?\d{4}",                  # Singapore
    r"05\d[\s\-]?\d{3}[\s\-]?\d{4}",                  # UAE local 05x
    r"\+\d{1,3}[\s\-]?\d{8,12}",                      # Generic international
]

EMAIL_PATTERN = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"


async def ddg_search(query: str, max_results: int = 5) -> List[dict]:
    """Free DuckDuckGo search."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=12, headers=HEADERS) as client:
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
        print(f"[ContactFinder] Search error: {e}")
    return results


async def fetch_page_text(url: str) -> str:
    """Fetch a webpage and return its text content."""
    if not url or not url.startswith("http"):
        return ""
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await client.get(url, follow_redirects=True)
            soup = BeautifulSoup(resp.text, "lxml")
            return soup.get_text(separator=" ", strip=True)[:3000]
    except Exception:
        return ""


def extract_phones_from_text(text: str) -> List[str]:
    """Extract all phone numbers from text."""
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            # Clean up the number
            clean = re.sub(r"[\s\-\(\)]", "", match)
            if len(clean) >= 8 and clean not in phones:
                phones.append(clean)
    return phones[:3]  # Return max 3 numbers


def extract_emails_from_text(text: str) -> List[str]:
    """Extract all email addresses from text."""
    emails = re.findall(EMAIL_PATTERN, text)
    # Filter out common false positives
    filtered = [
        e for e in emails
        if not any(skip in e.lower() for skip in [
            "example", "test", "noreply", "no-reply",
            "support", "admin", "info@linkedin", "info@facebook"
        ])
    ]
    return list(dict.fromkeys(filtered))[:3]  # Deduplicated, max 3


async def find_linkedin_url(name: str, company: str) -> Optional[str]:
    """Search for LinkedIn profile URL."""
    try:
        query = f"site:linkedin.com/in {name} {company or ''} Dubai real estate"
        results = await ddg_search(query, max_results=3)
        for r in results:
            url = r.get("url", "")
            if "linkedin.com/in/" in url:
                return "https://" + url if not url.startswith("http") else url
    except Exception:
        pass
    return None


async def find_contact_details(name: str, company: str) -> dict:
    """
    Search multiple free sources for phone and email.
    Tries: company website, WhatsApp business, Google Business Profile,
    property portal profiles, forum posts.
    """
    contacts = {"email": None, "phone": None}

    if not name or name in ["Unknown", "LinkedIn Profile"]:
        return contacts

    search_queries = [
        f'"{name}" Dubai real estate contact phone email',
        f'"{name}" {company or "property"} Dubai phone number',
        f'"{name}" whatsapp Dubai investor contact',
        f'"{name}" {company or ""} email contact UAE',
    ]
    if company:
        search_queries.append(f'"{company}" Dubai contact phone email site:.com')

    all_text = ""

    for query in search_queries[:3]:  # Limit to 3 searches per lead
        try:
            results = await ddg_search(query, max_results=4)
            for r in results:
                combined = f"{r.get('title', '')} {r.get('snippet', '')}"
                all_text += " " + combined

                # Try fetching the page for richer contact data
                # Only fetch non-social-media pages (they block bots)
                url = r.get("url", "")
                if url and not any(s in url for s in [
                    "linkedin", "facebook", "instagram",
                    "twitter", "youtube", "google"
                ]):
                    page_text = await fetch_page_text(
                        "https://" + url if not url.startswith("http") else url
                    )
                    all_text += " " + page_text

            await asyncio.sleep(1)
        except Exception as e:
            print(f"[ContactFinder] Query error: {e}")
            continue

    # Extract from all gathered text
    phones = extract_phones_from_text(all_text)
    emails = extract_emails_from_text(all_text)

    if phones:
        contacts["phone"] = phones[0]
    if emails:
        contacts["email"] = emails[0]

    return contacts


async def find_email_from_company(name: str, company: str) -> Optional[str]:
    """Guess email from company domain as fallback."""
    if not company:
        return None
    try:
        query = f"{company} official website"
        results = await ddg_search(query, max_results=2)
        for r in results:
            url = r.get("url", "")
            domain_match = re.search(r"([a-z0-9\-]+\.[a-z]{2,})", url)
            if domain_match:
                domain = domain_match.group(1)
                if any(s in domain for s in [
                    "linkedin", "facebook", "twitter",
                    "google", "youtube", "instagram"
                ]):
                    continue
                parts = name.lower().split()
                if len(parts) >= 2:
                    first, last = parts[0], parts[-1]
                    # Try most common email patterns
                    return f"{first}.{last}@{domain}"
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════
# CONTACT FINDER — main entry point
# ══════════════════════════════════════════════════════════

async def run_contact_finder(leads: List[QualifiedLead]) -> List[QualifiedLead]:
    """
    Finds LinkedIn, email, and phone for top leads.
    Uses free DuckDuckGo searches + page scraping.
    """
    print(f"[ContactFinder] Finding contacts for {len(leads)} leads")
    high_priority = [l for l in leads if l.score >= 50]
    print(f"[ContactFinder] Processing {len(high_priority)} priority leads")

    for lead in high_priority[:12]:
        print(f"[ContactFinder] Looking up: {lead.name}")
        try:
            # 1. Find LinkedIn if not already set
            if not lead.linkedin and lead.name and "Profile" not in lead.name:
                linkedin = await find_linkedin_url(lead.name, lead.company or "")
                if linkedin:
                    lead.linkedin = linkedin
                    print(f"  ✓ LinkedIn: {linkedin}")

            # 2. Search for phone + email
            if not lead.phone or not lead.email:
                contacts = await find_contact_details(lead.name, lead.company or "")
                if contacts.get("phone") and not lead.phone:
                    lead.phone = contacts["phone"]
                    print(f"  ✓ Phone: {contacts['phone']}")
                if contacts.get("email") and not lead.email:
                    lead.email = contacts["email"]
                    print(f"  ✓ Email: {contacts['email']}")

            # 3. Fallback email guess from company domain
            if not lead.email and lead.company:
                guessed = await find_email_from_company(lead.name, lead.company)
                if guessed:
                    lead.email = guessed
                    print(f"  ~ Email (guessed): {guessed}")

            await asyncio.sleep(1.5)

        except Exception as e:
            print(f"[ContactFinder] Error for {lead.name}: {e}")
            continue

    found_phones = sum(1 for l in leads if l.phone)
    found_emails = sum(1 for l in leads if l.email)
    found_linkedin = sum(1 for l in leads if l.linkedin)
    print(f"[ContactFinder] Done — phones: {found_phones}, emails: {found_emails}, LinkedIn: {found_linkedin}")
    return leads


# ══════════════════════════════════════════════════════════
# REPORT GENERATOR
# ══════════════════════════════════════════════════════════

async def run_report_generator(leads: List[QualifiedLead], original_query: str) -> str:
    print(f"[ReportGenerator] Generating report for {len(leads)} leads")

    if not leads:
        return "No leads found. Try broadening your search query."

    source_counts = {}
    for lead in leads:
        source_counts[lead.source] = source_counts.get(lead.source, 0) + 1

    type_counts = {}
    for lead in leads:
        t = lead.investor_type or "Unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    locations = [l.location for l in leads if l.location and l.location != "Unknown"]
    top_locations = list(dict.fromkeys(locations))[:4]

    high  = len([l for l in leads if l.score >= 80])
    mid   = len([l for l in leads if 60 <= l.score < 80])
    low   = len([l for l in leads if l.score < 60])

    with_phone   = sum(1 for l in leads if l.phone)
    with_email   = sum(1 for l in leads if l.email)
    with_linkedin = sum(1 for l in leads if l.linkedin)

    sources_str   = ", ".join(f"{s} ({c})" for s, c in source_counts.items())
    types_str     = ", ".join(f"{t} ({c})" for t, c in type_counts.items())
    locations_str = ", ".join(top_locations) if top_locations else "Various"

    report = f"""Pipeline completed for: "{original_query}"

SUMMARY
───────
Total leads      : {len(leads)}
High priority 80+: {high}
Medium 60-79     : {mid}
Lower priority   : {low}

CONTACT INFO FOUND
──────────────────
Phone numbers    : {with_phone}
Email addresses  : {with_email}
LinkedIn profiles: {with_linkedin}

SOURCES
───────
{sources_str}

INVESTOR TYPES
──────────────
{types_str}

LOCATIONS
─────────
{locations_str}

TOP LEADS
─────────"""

    for i, lead in enumerate(leads[:5], 1):
        report += f"""
{i}. {lead.name}
   Score    : {lead.score}/100
   Type     : {lead.investor_type}
   Interest : {lead.interest}
   Budget   : {lead.budget_estimate}
   Phone    : {lead.phone or 'Not found'}
   Email    : {lead.email or 'Not found'}
   LinkedIn : {lead.linkedin or lead.source_url or 'N/A'}
   Signal   : {(lead.signal or '')[:100]}
   Approach : {lead.recommended_approach}
"""

    report += """
NEXT STEPS
──────────
1. Visit LinkedIn profiles of high-score leads directly
2. Call or WhatsApp any phone numbers found
3. Send personalized emails referencing their specific interest
4. Join the Facebook groups found and engage naturally
5. Run again with a more specific query for deeper results"""

    return report
