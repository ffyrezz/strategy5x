"""
/portfolio command — Detailed position list with P&L.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from bot.formatters import format_portfolio

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /portfolio command."""
    try:
        positions = db.get_active_positions()
    except Exception as exc:
        await update.message.reply_text(f"Error fetching positions: {exc}")
        return

    text = format_portfolio(positions)
    await update.message.reply_text(text)
