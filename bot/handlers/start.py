"""
/start command — Welcome message and system status.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import format_sgt, now_utc

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    lines = []

    # Check database connectivity
    try:
        db.get_client()
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    # Check for positions (broker sync freshness)
    sync_status = "no sync recorded yet"
    try:
        positions = db.get_active_positions()
        if positions:
            freshest = max(
                (p.get("source_fresh_at") for p in positions if p.get("source_fresh_at")),
                default=None,
            )
            if freshest:
                sync_status = f"last sync {freshest}"
    except Exception:
        sync_status = "cannot check"

    lines.append("Strategy 5.x bot online.")
    lines.append(f"Database: {db_status}.")
    lines.append(f"Broker sync: {sync_status}.")
    lines.append("Commands: /status /portfolio /brief /candidate /score /plan /concentration /ack /reflect")
    lines.append("Next: run /portfolio to confirm live holdings.")

    await update.message.reply_text("\n".join(lines))
