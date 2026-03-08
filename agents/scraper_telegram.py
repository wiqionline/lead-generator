"""
Telegram Scraper Agent
───────────────────────
Uses the Telethon library to read public Telegram channels
and groups related to Dubai real estate investment.

SETUP REQUIRED (one-time, free):
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click "API development tools"
4. Create an app — get API_ID and API_HASH
5. Add to your .env file

The script reads PUBLIC channels only — no login to private groups needed.
For private groups you'd need to be a member and use a user account.

Free — Telegram API has no cost.
"""
import asyncio
import re
from typing import List
from core.models import RawLead

# Public Dubai real estate Telegram channels/groups to monitor
PUBLIC_CHANNELS = [
    "dubaipropertyinvestors",
    "dubairealestateinvestment",
    "offplandubai",
    "dubaipropertynews",
    "emiratespropertyinvestors",
    "dubaiinvestors",
    "uaerealestate",
    "dubairealty",
]

INVESTMENT_KEYWORDS = [
    "invest", "investor", "off-plan", "off plan", "buy", "purchase",
    "looking for property", "interested in", "ROI", "yield", "portfolio",
    "payment plan", "JV", "joint venture", "capital", "budget",
    "seeking", "want to buy", "interested to invest", "off plan dubai"
]

NAME_PATTERNS = [
    r"(?:I am|I'm|My name is|Call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"(?:Contact|reach)\s+([A-Z][a-z]+)",
]


def extract_intent_signals(text: str) -> bool:
    """Check if a message contains strong investment intent signals."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in INVESTMENT_KEYWORDS)


def extract_name_from_message(text: str) -> str:
    """Try to extract a person's name from message text."""
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "Telegram User"


async def run_telegram_scraper(user_query: str) -> List[RawLead]:
    """
    Main Telegram scraper entry point.
    Requires TELEGRAM_API_ID and TELEGRAM_API_HASH in environment.
    Falls back gracefully if credentials are not set.
    """
    import os
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not api_id or not api_hash:
        print("[Telegram] No credentials found — skipping Telegram scrape")
        print("[Telegram] Add TELEGRAM_API_ID and TELEGRAM_API_HASH to .env to enable")
        return []

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError, ChannelPrivateError
        from telethon.tl.types import Channel, Chat

        print(f"[Telegram] Starting scrape of {len(PUBLIC_CHANNELS)} channels")
        leads: List[RawLead] = []

        # Use a session file so you only authenticate once
        client = TelegramClient("leadgen_session", int(api_id), api_hash)
        await client.start(phone=phone)

        for channel_username in PUBLIC_CHANNELS:
            try:
                print(f"[Telegram] Scanning @{channel_username}")
                entity = await client.get_entity(channel_username)

                # Read last 50 messages from each channel
                async for message in client.iter_messages(entity, limit=50):
                    if not message.text:
                        continue
                    text = message.text.strip()
                    if len(text) < 20:
                        continue
                    if not extract_intent_signals(text):
                        continue

                    # Get sender info if available
                    sender_name = "Telegram User"
                    try:
                        sender = await message.get_sender()
                        if sender:
                            first = getattr(sender, "first_name", "") or ""
                            last = getattr(sender, "last_name", "") or ""
                            username = getattr(sender, "username", "") or ""
                            sender_name = f"{first} {last}".strip() or username or "Telegram User"
                    except Exception:
                        sender_name = extract_name_from_message(text)

                    source_url = f"https://t.me/{channel_username}/{message.id}"

                    leads.append(RawLead(
                        name=sender_name,
                        source_url=source_url,
                        raw_text=f"[{channel_username}] {text[:500]}",
                        platform="telegram"
                    ))

                await asyncio.sleep(1)  # Be respectful of rate limits

            except ChannelPrivateError:
                print(f"[Telegram] @{channel_username} is private — skipping")
            except FloodWaitError as e:
                print(f"[Telegram] Rate limited — waiting {e.seconds}s")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"[Telegram] Error on @{channel_username}: {e}")
                continue

        await client.disconnect()
        print(f"[Telegram] Found {len(leads)} investment signals")
        return leads

    except ImportError:
        print("[Telegram] Telethon not installed — run: pip install telethon")
        return []
    except Exception as e:
        print(f"[Telegram] Fatal error: {e}")
        return []
