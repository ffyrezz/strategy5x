"""
/concentration — Show portfolio concentration breakdown.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import db
from bot.formatters import format_concentration

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /concentration command."""
    try:
        positions = db.get_active_positions()
    except Exception as exc:
        await update.message.reply_text(f"Error fetching positions: {exc}")
        return

    if not positions:
        await update.message.reply_text("No live positions found.")
        return

    text = format_concentration(positions, config.SINGLE_NAME_CAP_PCT)
    await update.message.reply_text(text)
