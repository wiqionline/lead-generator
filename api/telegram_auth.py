"""
Telegram One-Time Authentication Endpoint
──────────────────────────────────────────
Handles the first-time Telegram login from browser.
Only needed ONCE — after that the session is saved.
"""
import os
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

auth_router = APIRouter()

class CodeInput(BaseModel):
    code: str

class PasswordInput(BaseModel):
    password: str

# Global client state
_client = None
_phone_code_hash = None


@auth_router.post("/telegram/send-code")
async def send_code():
    """
    Step 1 — Send verification code to your Telegram app.
    Call this first, then check your Telegram for the code.
    """
    global _client, _phone_code_hash

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not all([api_id, api_hash, phone]):
        return {"error": "Missing TELEGRAM_API_ID, TELEGRAM_API_HASH or TELEGRAM_PHONE in variables"}

    try:
        from telethon import TelegramClient
        _client = TelegramClient(
            "leadgen_session",
            int(api_id),
            api_hash,
            system_version="4.16.30-vxCUSTOM"
        )
        await _client.connect()

        # Check if already authorized
        if await _client.is_user_authorized():
            return {
                "status": "already_authorized",
                "message": "Telegram is already connected! You can run the pipeline."
            }

        # Send code to phone
        result = await _client.send_code_request(phone)
        _phone_code_hash = result.phone_code_hash

        return {
            "status": "code_sent",
            "message": f"Code sent to {phone} via Telegram. Now call POST /telegram/verify-code with the code."
        }

    except Exception as e:
        return {"error": str(e)}


@auth_router.post("/telegram/verify-code")
async def verify_code(body: CodeInput):
    """
    Step 2 — Enter the code you received on Telegram.
    """
    global _client, _phone_code_hash

    phone = os.getenv("TELEGRAM_PHONE")

    if not _client:
        return {"error": "Call /telegram/send-code first"}

    try:
        await _client.sign_in(phone, body.code, phone_code_hash=_phone_code_hash)
        await _client.disconnect()
        return {
            "status": "success",
            "message": "Telegram authenticated! Session saved. You can now run the pipeline."
        }
    except Exception as e:
        error_str = str(e)
        # Two-factor auth needed
        if "Two-steps" in error_str or "password" in error_str.lower():
            return {
                "status": "2fa_required",
                "message": "Two-factor auth enabled. Call POST /telegram/verify-password with your Telegram password."
            }
        return {"error": error_str}


@auth_router.post("/telegram/verify-password")
async def verify_password(body: PasswordInput):
    """
    Step 3 (only if you have 2FA) — Enter your Telegram password.
    """
    global _client

    if not _client:
        return {"error": "Call /telegram/send-code first"}

    try:
        await _client.sign_in(password=body.password)
        await _client.disconnect()
        return {
            "status": "success",
            "message": "Telegram authenticated with 2FA! Session saved. Pipeline is ready."
        }
    except Exception as e:
        return {"error": str(e)}


@auth_router.get("/telegram/status")
async def telegram_status():
    """Check if Telegram is authenticated."""
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        return {"status": "not_configured", "message": "Add TELEGRAM_API_ID and TELEGRAM_API_HASH to variables"}

    try:
        from telethon import TelegramClient
        client = TelegramClient(
            "leadgen_session",
            int(api_id),
            api_hash,
            system_version="4.16.30-vxCUSTOM"
        )
        await client.connect()
        authorized = await client.is_user_authorized()
        await client.disconnect()

        if authorized:
            return {"status": "connected", "message": "Telegram is authenticated and ready"}
        else:
            return {"status": "not_authenticated", "message": "Call POST /telegram/send-code to authenticate"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
