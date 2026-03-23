"""
Telegram message sender with retry and exponential backoff.

Replaces direct httpx calls in jobs. Retries up to 3 times (1s, 3s, 9s).
Logs delivery failures to the alerts table.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

import config
import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds; retries at 1s, 3s, 9s


async def send_message(text: str, chat_id: str | None = None) -> bool:
    """
    Send a Telegram message with retry/backoff.

    Returns True on success, False after all retries exhausted.
    """
    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={
                        "chat_id": target_chat,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    return True

                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(
                    "Telegram send attempt %d/%d failed: %s",
                    attempt + 1, MAX_RETRIES, last_error,
                )

                # Rate limit (429) — respect Retry-After if present
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", BACKOFF_BASE * (3 ** attempt)))
                    await asyncio.sleep(retry_after)
                    continue

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Telegram send attempt %d/%d exception: %s",
                attempt + 1, MAX_RETRIES, exc,
            )

        if attempt < MAX_RETRIES - 1:
            delay = BACKOFF_BASE * (3 ** attempt)
            await asyncio.sleep(delay)

    logger.error("Telegram send failed after %d attempts: %s", MAX_RETRIES, last_error)

    # Log failure to alerts table
    try:
        db.log_error_alert("telegram_sender", f"Send failed after {MAX_RETRIES} retries: {last_error}")
    except Exception:
        pass

    return False
