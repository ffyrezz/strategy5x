"""
/export — Export all Supabase data to CSV files.

Usage:
  /export — dump all tables to timestamped CSV directory
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from jobs.export_data import run_export, format_export_summary

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export command."""
    await update.message.reply_text("Exporting data... this may take a moment.")

    try:
        export_dir, results = run_export()
        summary = format_export_summary(export_dir, results)
        await update.message.reply_text(summary)

    except Exception as exc:
        logger.error("Export failed: %s", exc, exc_info=True)
        await update.message.reply_text(f"Export failed: {exc}")
