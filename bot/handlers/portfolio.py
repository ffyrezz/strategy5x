"""
/portfolio command — Detailed position list with P&L.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from bot.formatters import format_portfolio
from data.market_data import get_price_data

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /portfolio command."""
    try:
        positions = db.get_active_positions()
    except Exception as exc:
        await update.message.reply_text(f"Error fetching positions: {exc}")
        return

    # Enrich with live prices including extended hours
    for pos in positions:
        try:
            pd = get_price_data(pos["ticker"])
            if pd.get("price"):
                pos["last_price"] = pd["price"]
                qty = float(pos.get("quantity", 0))
                avg = float(pos.get("avg_cost", 0))
                pos["market_value"] = qty * pd["price"]
                if avg > 0:
                    pos["unrealized_pnl"] = qty * (pd["price"] - avg)
                    pos["unrealized_pnl_pct"] = ((pd["price"] - avg) / avg) * 100
            if pd.get("previous_close"):
                pos["previous_close"] = pd["previous_close"]
            if pd.get("pre_market_price"):
                pos["pre_market_price"] = pd["pre_market_price"]
            if pd.get("post_market_price"):
                pos["post_market_price"] = pd["post_market_price"]
        except Exception:
            pass

    text = format_portfolio(positions)
    await update.message.reply_text(text)
