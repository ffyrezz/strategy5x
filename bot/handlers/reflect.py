"""
/reflect TICKER "reflection text" — Log post-trade reflection.

Usage:
  /reflect                              — show pending reflections
  /reflect RCKT "Sold too early, should have held through approval"
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _parse_reflect_args(args: list[str]) -> tuple[str, str]:
    """
    Parse reflection command args.

    Returns (ticker, reflection_text).
    Handles: /reflect RCKT "some text here"
    Also handles: /reflect RCKT some text here (unquoted)
    """
    if not args:
        return "", ""

    ticker = args[0].upper()
    raw = " ".join(args[1:])

    # Try quoted text first
    match = re.search(r'"([^"]+)"', raw)
    if match:
        return ticker, match.group(1)

    # Fall back to everything after ticker
    return ticker, raw.strip()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reflect command."""
    args = context.args or []
    ticker, reflection_text = _parse_reflect_args(args)

    # No args: show pending reflections
    if not ticker:
        try:
            unreflected = db.get_unreflected_trades()
            if not unreflected:
                await update.message.reply_text("No pending trade reflections.")
                return

            lines = ["Pending reflections:"]
            for trade in unreflected[:5]:
                t = trade.get("ticker", "?")
                filled = trade.get("filled_at", "?")
                lines.append(f"  {t} — exited {str(filled)[:10]}")
            lines.append("")
            lines.append('Usage: /reflect TICKER "what I learned from this trade"')
            await update.message.reply_text("\n".join(lines))
        except Exception as exc:
            await update.message.reply_text(f"Error fetching reflections: {exc}")
        return

    # Validate reflection text
    if not reflection_text:
        await update.message.reply_text(
            f'Usage: /reflect {ticker} "what I learned from this trade"\n'
            "Reflection text is required."
        )
        return

    if len(reflection_text) < 10:
        await update.message.reply_text(
            "Reflection too short. What did you learn from this trade? (min 10 chars)"
        )
        return

    # Find the most recent unreflected SELL trade for this ticker
    trades = db.get_recent_trades(ticker=ticker, limit=5)
    sell_trades = [
        t for t in trades
        if t.get("side") == "SELL" and not t.get("reflection_completed")
    ]

    if not sell_trades:
        await update.message.reply_text(f"No unreflected exit trades found for {ticker}.")
        return

    trade = sell_trades[0]
    trade_id = trade["id"]

    try:
        # Update the trade record
        db.update_trade(trade_id, {
            "reflection_completed": True,
            "notes": f"Reflection: {reflection_text}",
        })

        # Determine plan adherence metric value
        plan_adherence = trade.get("plan_adherence")
        if plan_adherence == "followed":
            metric_value = 1.0
        elif plan_adherence == "deviated":
            metric_value = 0.0
        else:
            metric_value = 0.5  # no_plan or null

        # Insert behavioral metric
        now = now_utc()
        db.insert_behavioral_metric({
            "metric_type": "plan_adherence",
            "reference_type": "trade",
            "reference_id": trade_id,
            "ticker": ticker,
            "metric_value": metric_value,
            "metric_unit": "ratio",
            "context": {"reflection": reflection_text, "plan_adherence": plan_adherence},
            "observed_at": now.isoformat(),
            "created_at": now.isoformat(),
        })

        lines = [
            f"Reflection saved for {ticker} trade.",
            f"Plan adherence: {plan_adherence or 'unknown'} (metric: {metric_value})",
            "This reflection will appear in the next weekly audit snapshot.",
        ]
        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("Failed to save reflection: %s", exc, exc_info=True)
        await update.message.reply_text(f"Error saving reflection: {exc}")
