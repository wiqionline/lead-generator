"""
AGENT 4 — Telegram Intent Monitor
Scans verified active Dubai RE groups for buyer intent.
"""
import asyncio
import re
import os
from typing import List, Optional
from core.models import RawLead

# ── VERIFIED active Dubai RE Telegram groups (March 2026) ─
GROUPS = [
    # VERIFIED active groups — real usernames from Telegram search
    "secondary_dubai",           # Property Portal UAE | Secondary Resale — 12,222 members
    "real_estate_property_dubai", # DUBAI REAL ESTATE PROPERTY RESALE — 8,058 members
    "distress_deal",             # Distress deals Dubai Property — 4,995 members
    "makalex_hot_property",      # Makalex Hot Property Dubai — 1,283 members
    "propertyfromowner",         # Property From Owner in Dubai — 1,254 members
    "discount_property_dubai",   # Dubai Property Discount — 564 members
    "dubai_propertyy",           # Dubai Property — 682 members
    "CapitalVenturesinvestors",  # Real estate Dubai 369Capital — 606 members
    "dubairealestate_investment", # Dubai Real Estate Investment — 250 members
    "brandedhomes_ae",           # Branded Residences Property — 228 members
    "dubairealestate_investment", # Dubai Real Estate Investment
    "offplandxb",               # Dubai off plan
    "offplanprojects",          # Dubai off plan projects
    "insideallprojects_ae",     # Inside New Off-Plan Launches
    "Dubailuxuryy",             # REAL ESTATE DUBAI INVESTORS
]

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
    "reliable developer", "which project", "aed 2", "aed 3", "aed 5",
    "2 million", "3 million", "5 million", "2m budget", "3m budget",
]

SPAM_SIGNALS = [
    "we offer", "we have", "available now", "book now", "register",
    "limited units", "don't miss", "special offer", "launching",
    "new project", "for sale", "sqft", "sq.ft",
    "1% monthly", "0% commission", "call us",
    "whatsapp us", "contact us", "our team",
    "studio from", "1br from", "2br from", "3br from",
    "price from", "starting from", "starting at",
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
    tl = text.lower()
    spam_hits = sum(1 for s in SPAM_SIGNALS if s in tl)
    if spam_hits >= 2:
        return "spam"
    buyer_hits = sum(1 for s in BUYER_SIGNALS if s in tl)
    if buyer_hits >= 1:
        return "buyer"
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
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not all([api_id, api_hash, phone]):
        print("[Agent4:Telegram] No credentials — skipping")
        return []

    try:
        from telethon import TelegramClient
        from telethon.errors import (
            ChannelPrivateError, FloodWaitError,
            UsernameNotOccupiedError, UsernameInvalidError
        )
        from telethon.tl.types import User, Channel

        leads: List[RawLead] = []
        working_groups = []
        failed_groups = []

        client = TelegramClient(
            "leadgen_session", int(api_id), api_hash,
            system_version="4.16.30-vxCUSTOM"
        )

        await client.start(phone=phone)
        print(f"[Agent4:Telegram] Connected — testing {len(GROUPS)} groups")

        for group in GROUPS:
            try:
                entity = await client.get_entity(group)
                # Check it's a real group/channel with members
                if hasattr(entity, 'participants_count'):
                    count = entity.participants_count or 0
                    if count < 100:
                        print(f"[Agent4:Telegram] @{group}: too small ({count} members) — skipping")
                        continue

                working_groups.append((group, entity))
                print(f"[Agent4:Telegram] ✓ @{group} — active")
                await asyncio.sleep(0.5)

            except (UsernameNotOccupiedError, UsernameInvalidError):
                failed_groups.append(group)
            except ChannelPrivateError:
                print(f"[Agent4:Telegram] @{group} is private")
                failed_groups.append(group)
            except Exception as e:
                failed_groups.append(group)

        print(f"[Agent4:Telegram] {len(working_groups)} active groups found, {len(failed_groups)} failed")

        # Also scan groups you're already a member of
        print(f"[Agent4:Telegram] Scanning your joined groups too...")
        try:
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    name = dialog.name or ""
                    if any(kw in name.lower() for kw in [
                        "dubai", "property", "real estate", "invest",
                        "uae", "gulf", "emaar", "damac", "off plan"
                    ]):
                        already = any(g == dialog.entity for _, g in working_groups)
                        if not already:
                            working_groups.append((name, dialog.entity))
                            print(f"[Agent4:Telegram] + Joined group: {name}")
        except Exception as e:
            print(f"[Agent4:Telegram] Dialog scan error: {e}")

        # Scan all working groups for buyer intent
        for group_name, entity in working_groups:
            try:
                total = 0
                found = 0

                async for msg in client.iter_messages(entity, limit=300):
                    if not msg.text or len(msg.text.strip()) < 20:
                        continue
                    total += 1
                    text = msg.text.strip()

                    if classify_message(text) != "buyer":
                        continue

                    found += 1

                    # Get sender details
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
                        gid = getattr(entity, "username", None) or str(getattr(entity, "id", ""))
                        source_url = f"https://t.me/{gid}/{msg.id}" if gid else f"https://t.me/c/{msg.id}"
                    except Exception:
                        source_url = "https://t.me"

                    raw = (
                        f"[TELEGRAM: {group_name}]\n"
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

                print(f"[Agent4:Telegram] {group_name}: {total} msgs → {found} buyer signals")
                await asyncio.sleep(1)

            except FloodWaitError as e:
                print(f"[Agent4:Telegram] Rate limited — waiting {e.seconds}s")
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                print(f"[Agent4:Telegram] Error {group_name}: {e}")

        await client.disconnect()
        print(f"[Agent4:Telegram] Done — {len(leads)} genuine buyer signals")
        return leads

    except Exception as e:
        print(f"[Agent4:Telegram] Fatal: {e}")
        return []
