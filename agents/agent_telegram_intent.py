"""
AGENT 4 — Telegram Intent Monitor
───────────────────────────────────
Specific task: Read Telegram groups and find ONLY messages
where a real person is expressing genuine buyer intent.

Filters OUT:
- Agent listings ("We have 1BR from AED 800K")
- Spam ("Book now! Limited units!")
- News/announcements

Keeps ONLY:
- Questions ("Which area has best ROI?")
- Buying signals ("Looking for off-plan 2M budget")
- Advice requests ("Anyone recommend a developer?")
- Budget mentions from buyers ("My budget is AED 3M")

Output: Real person name + message + phone (if shared) + Telegram username
"""
import asyncio
import re
import os
from typing import List, Optional
from core.models import RawLead

# Best Dubai RE investor Telegram groups
GROUPS = [
    "dubaipropertyinvestors",
    "dubairealestateinvestment",
    "offplandubai",
    "dubaiinvestors",
    "uaerealestate",
    "emiratespropertyinvestors",
    "dubaipropertymarket",
    "investindubai",
    "dubaiproperty",
    "gulfpropertyinvestors",
    "dubaioffplan",
    "uaepropertyinvestors",
]

# Genuine buyer signals — person is SEEKING not selling
BUYER_SIGNALS = [
    "looking for", "looking to buy", "want to buy", "want to invest",
    "planning to buy", "planning to invest", "interested in buying",
    "searching for", "which area", "which developer", "best developer",
    "best area", "good roi", "high yield", "recommend", "suggestion",
    "where to invest", "how to invest", "first time", "my budget",
    "budget is", "have aed", "can afford", "payment plan options",
    "off plan recommendation", "anyone know", "can anyone", "help me",
    "advice", "opinion", "thoughts on", "experience with",
    "is it worth", "good investment", "safe to invest",
    "reliable developer", "which project",
]

# Spam patterns — agent/developer posts
SPAM_SIGNALS = [
    "we offer", "we have", "available now", "book now", "register",
    "limited units", "don't miss", "special offer", "launching",
    "new project", "for sale", "sqft", "sq.ft", "handover",
    "payment plan:", "1% monthly", "0% commission", "call us",
    "whatsapp us", "contact us", "our team", "click link",
    "t.me/+", "bit.ly", "shortlink", "promo", "discount",
    "studio from", "1br from", "2br from", "3br from",
]

PHONE_RE = re.compile(
    r"(\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}"
    r"|05\d[\s\-]?\d{3}[\s\-]?\d{4}"
    r"|\+\d{1,3}[\s\-]?\d{8,12})"
)

BUDGET_RE = re.compile(
    r"(?:aed|budget|have)\s*(\d+(?:\.\d+)?)\s*(?:million|m\b|k\b)?",
    re.IGNORECASE
)


def classify_message(text: str) -> str:
    """
    Returns: 'buyer' | 'spam' | 'ignore'
    """
    tl = text.lower()
    spam_hits = sum(1 for s in SPAM_SIGNALS if s in tl)
    if spam_hits >= 2:
        return "spam"
    buyer_hits = sum(1 for s in BUYER_SIGNALS if s in tl)
    if buyer_hits >= 1:
        return "buyer"
    # Phone number shared + Dubai property mention = likely buyer
    if PHONE_RE.search(text) and any(w in tl for w in ["dubai", "property", "invest", "aed"]):
        return "buyer"
    return "ignore"


def extract_phone(text: str) -> Optional[str]:
    match = PHONE_RE.search(text)
    if match:
        return re.sub(r"[\s\-]", "", match.group())
    return None


def extract_budget(text: str) -> str:
    match = BUDGET_RE.search(text)
    if match:
        val = float(match.group(1))
        if val < 100:
            return f"AED {val}M"
        elif val < 10000:
            return f"AED {val}K"
        else:
            return f"AED {val:,.0f}"
    return "Unknown"


async def run_telegram_intent_agent(user_query: str) -> List[RawLead]:
    """
    AGENT 4 — Pure intent filter for Telegram.
    Only returns genuine buyer messages, zero agent spam.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not all([api_id, api_hash, phone]):
        print("[Agent4:Telegram] No credentials — skipping")
        return []

    try:
        from telethon import TelegramClient
        from telethon.errors import ChannelPrivateError, FloodWaitError
        from telethon.tl.types import User

        leads: List[RawLead] = []
        client = TelegramClient(
            "leadgen_session", int(api_id), api_hash,
            system_version="4.16.30-vxCUSTOM"
        )

        await client.start(phone=phone)
        print(f"[Agent4:Telegram] Connected — scanning {len(GROUPS)} groups")

        for group in GROUPS:
            try:
                entity = await client.get_entity(group)
                total = 0
                found = 0

                async for msg in client.iter_messages(entity, limit=200):
                    if not msg.text or len(msg.text.strip()) < 20:
                        continue
                    total += 1
                    text = msg.text.strip()
                    classification = classify_message(text)

                    if classification != "buyer":
                        continue

                    found += 1

                    # Get real sender details
                    name = "Telegram User"
                    username = ""
                    try:
                        sender = await msg.get_sender()
                        if sender and isinstance(sender, User):
                            first = getattr(sender, "first_name", "") or ""
                            last = getattr(sender, "last_name", "") or ""
                            username = getattr(sender, "username", "") or ""
                            name = f"{first} {last}".strip() or username or "Telegram User"
                    except Exception:
                        pass

                    phone_in_msg = extract_phone(text)
                    budget = extract_budget(text)

                    try:
                        group_name = getattr(entity, "username", group)
                        source_url = f"https://t.me/{group_name}/{msg.id}"
                    except Exception:
                        source_url = f"https://t.me/{group}"

                    raw = (
                        f"[TELEGRAM @{group} — BUYER INTENT]\n"
                        f"Name: {name}\n"
                        f"Username: @{username}\n"
                        f"Phone shared: {phone_in_msg or 'none'}\n"
                        f"Budget signal: {budget}\n"
                        f"Message: {text[:400]}"
                    )

                    leads.append(RawLead(
                        name=name,
                        source_url=source_url,
                        raw_text=raw,
                        platform="telegram"
                    ))

                print(f"[Agent4:Telegram] @{group}: {total} msgs → {found} buyer signals")
                await asyncio.sleep(1.5)

            except ChannelPrivateError:
                print(f"[Agent4:Telegram] @{group} is private — skipping")
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                print(f"[Agent4:Telegram] Error @{group}: {e}")

        await client.disconnect()
        print(f"[Agent4:Telegram] Done — {len(leads)} genuine buyer signals")
        return leads

    except Exception as e:
        print(f"[Agent4:Telegram] Fatal: {e}")
        return []
