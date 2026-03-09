"""
Telegram Organic Intent Monitor
─────────────────────────────────
Monitors PUBLIC and PRIVATE Telegram groups you're a member of.
Finds real people posting genuine investment intent messages.

Examples of what it catches:
- "Looking for off-plan in Dubai Marina, budget 3M"
- "Anyone recommend good developer for investment apartments?"
- "I want to buy property in Dubai, where to start?"
- "Which areas give best ROI in Dubai?"

Setup (free, one time):
1. Go to https://my.telegram.org
2. Log in → API development tools → Create app
3. Add TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE to Railway vars
"""
import asyncio
import re
import os
from typing import List, Optional
from core.models import RawLead

# ── Public Dubai RE investor groups to monitor ─────────────
# Add more as you discover them
PUBLIC_GROUPS = [
    # Public channels — no membership needed
    "dubaipropertyinvestors",
    "dubairealestateinvestment",
    "offplandubai",
    "dubaipropertynews",
    "emiratespropertyinvestors",
    "dubaiinvestors",
    "uaerealestate",
    "dubairealty",
    "dubaipropertymarket",
    "investindubai",
    "dubaiproperty",
    "uaepropertyinvestors",
    "gulfpropertyinvestors",
    "dubaioffplan",
]

# ── Strong buyer intent phrases ────────────────────────────
BUYER_INTENT = [
    # Direct buying signals
    "looking for", "looking to buy", "want to buy", "want to invest",
    "planning to buy", "planning to invest", "interested in buying",
    "interested in investing", "searching for property",
    "need help finding", "recommend", "suggestions",
    "which area", "which developer", "best developer",
    "best area for investment", "good roi", "high yield",
    "payment plan", "off plan recommendation",
    # Budget signals
    "budget", "aed", "million", "m budget", "my budget",
    "can afford", "have aed", "have budget",
    # Question signals (people seeking to invest ask questions)
    "where to invest", "how to invest", "best time to buy",
    "is it good time", "worth investing", "good investment",
    "which project", "which developer", "emaar or damac",
    # Contact sharing
    "whatsapp", "call me", "dm me", "contact me",
    "reach me", "ping me", "message me",
]

# ── Spam/agent signals to filter OUT ──────────────────────
AGENT_SPAM = [
    "we offer", "we have", "we are offering", "contact our agent",
    "our properties", "exclusive listing", "limited units",
    "book now", "register now", "don't miss", "hurry",
    "special discount", "launch price", "click here",
    "www.", "http", "t.me/", "bit.ly", "shortlink",
    "for sale", "sqft", "sq ft", "studio from",
    "1br from", "2br from", "price from",
]

# ── Name extraction patterns ───────────────────────────────
NAME_PATTERNS = [
    r"(?:I[''`]m|I am|My name is|This is|Hi[,\s]+I[''`]m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"^([A-Z][a-z]+ [A-Z][a-z]+)[\s:,]",
    r"(?:call|contact|reach)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
]

PHONE_PATTERNS = [
    r"\+971[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{4}",
    r"05\d[\s\-]?\d{3}[\s\-]?\d{4}",
    r"\+\d{1,3}[\s\-]?\d{8,12}",
]


def is_buyer_intent(text: str) -> bool:
    """Check if message contains genuine buyer intent."""
    text_lower = text.lower()
    # Must have at least one buyer intent phrase
    has_intent = any(phrase in text_lower for phrase in BUYER_INTENT)
    # Must NOT look like agent spam
    is_spam = sum(1 for spam in AGENT_SPAM if spam in text_lower) >= 2
    return has_intent and not is_spam


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from message."""
    for pattern in PHONE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"[\s\-]", "", match.group())
    return None


def extract_name(text: str, sender_name: str) -> str:
    """Extract name — prefer sender name, fall back to text patterns."""
    if sender_name and sender_name not in ["", "None", "Telegram User"]:
        return sender_name
    for pattern in NAME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return "Telegram User"


def extract_budget(text: str) -> str:
    """Extract budget from message."""
    # AED patterns
    aed_match = re.search(r"(?:aed|budget)[^\d]*(\d[\d,.]+)(?:\s*(?:million|m|k))?", text.lower())
    if aed_match:
        val = aed_match.group(1).replace(",", "")
        try:
            num = float(val)
            if num > 100000:
                return f"AED {num:,.0f}"
            elif num > 100:
                return f"AED {num}K"
            else:
                return f"AED {num}M"
        except Exception:
            pass

    # Million patterns
    mil_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:million|m)\b", text.lower())
    if mil_match:
        return f"AED {mil_match.group(1)}M"

    return "Unknown"


def score_message(text: str) -> int:
    """Score a message for lead quality 0-100."""
    score = 30  # Base score for passing intent filter
    text_lower = text.lower()

    # Budget mentioned = strong signal
    if any(w in text_lower for w in ["aed", "budget", "million", "afford"]):
        score += 20

    # Phone number shared = very strong signal
    if extract_phone(text):
        score += 25

    # Specific area mentioned
    areas = ["marina", "downtown", "palm", "jumeirah", "business bay", "creek", "hills"]
    if any(area in text_lower for area in areas):
        score += 10

    # Specific developer mentioned
    devs = ["emaar", "damac", "nakheel", "meraas", "sobha", "aldar", "ellington"]
    if any(dev in text_lower for dev in devs):
        score += 10

    # Question asked = genuine seeker
    if "?" in text:
        score += 5

    # Length — longer messages = more genuine
    if len(text) > 100:
        score += 5

    return min(score, 100)


async def run_telegram_monitor(user_query: str) -> List[RawLead]:
    """
    Monitor Telegram groups for real buyer intent messages.
    Returns only genuine leads — filters out agent spam.
    """
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not api_id or not api_hash:
        print("[Telegram] No credentials — skipping")
        print("[Telegram] Add TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE to Railway variables")
        return []

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
        from telethon.tl.types import User

        print(f"[Telegram] Connecting...")
        leads: List[RawLead] = []

        client = TelegramClient(
            "leadgen_session",
            int(api_id),
            api_hash,
            system_version="4.16.30-vxCUSTOM"
        )

        await client.start(phone=phone)
        print(f"[Telegram] Connected — scanning {len(PUBLIC_GROUPS)} groups")

        for group_username in PUBLIC_GROUPS:
            try:
                print(f"[Telegram] Scanning @{group_username}...")
                entity = await client.get_entity(group_username)

                message_count = 0
                lead_count = 0

                # Scan last 100 messages per group
                async for message in client.iter_messages(entity, limit=100):
                    if not message.text:
                        continue
                    text = message.text.strip()
                    if len(text) < 25:
                        continue

                    message_count += 1

                    # Filter for genuine buyer intent only
                    if not is_buyer_intent(text):
                        continue

                    # Get sender details
                    sender_name = "Telegram User"
                    sender_username = ""
                    sender_phone = None

                    try:
                        sender = await message.get_sender()
                        if sender and isinstance(sender, User):
                            first = getattr(sender, "first_name", "") or ""
                            last = getattr(sender, "last_name", "") or ""
                            sender_username = getattr(sender, "username", "") or ""
                            sender_name = f"{first} {last}".strip() or sender_username or "Telegram User"
                    except Exception:
                        pass

                    # Extract contact info from message
                    phone_in_msg = extract_phone(text)
                    name = extract_name(text, sender_name)
                    budget = extract_budget(text)
                    msg_score = score_message(text)

                    # Build source URL
                    try:
                        group_id = getattr(entity, "username", group_username)
                        source_url = f"https://t.me/{group_id}/{message.id}"
                    except Exception:
                        source_url = f"https://t.me/{group_username}"

                    # Build rich raw text
                    raw_text = (
                        f"[TELEGRAM @{group_username}]\n"
                        f"Name: {name}\n"
                        f"Username: @{sender_username}\n"
                        f"Phone in message: {phone_in_msg or 'not shared'}\n"
                        f"Budget: {budget}\n"
                        f"Message: {text[:400]}"
                    )

                    leads.append(RawLead(
                        name=name,
                        source_url=source_url,
                        raw_text=raw_text,
                        platform="telegram"
                    ))
                    lead_count += 1

                print(f"[Telegram] @{group_username}: {message_count} messages → {lead_count} buyer signals")
                await asyncio.sleep(1.5)  # Rate limit respect

            except ChannelPrivateError:
                print(f"[Telegram] @{group_username} is private — skipping")
            except UsernameNotOccupiedError:
                print(f"[Telegram] @{group_username} not found — skipping")
            except FloodWaitError as e:
                print(f"[Telegram] Rate limited — waiting {e.seconds}s")
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                print(f"[Telegram] Error on @{group_username}: {e}")
                continue

        await client.disconnect()
        print(f"[Telegram] Done — {len(leads)} genuine buyer signals found")
        return leads

    except ImportError:
        print("[Telegram] Telethon not installed")
        return []
    except Exception as e:
        print(f"[Telegram] Fatal error: {e}")
        return []
