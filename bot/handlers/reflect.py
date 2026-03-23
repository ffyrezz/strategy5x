"""
/reflect TICKER — Log post-trade reflection.

Usage:
  /reflect                                         — show pending reflections
  /reflect TICKER plan_followed=yes mistake="..."  — submit reflection
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _parse_reflect_args(args: list[str]) -> tuple[str, dict[str, str]]:
    """Parse reflection command args."""
    if not args:
        return "", {}

    ticker = args[0].upper()
    raw = " ".join(args[1:])

    kwargs = {}
    # Extract key="value" pairs
    for match in re.finditer(r'(\w+)="([^"]*)"', raw):
        kwargs[match.group(1).lower()] = match.group(2)

    # Unquoted key=value
    for arg in args[1:]:
        if "=" in arg and '"' not in arg:
            key, val = arg.split("=", 1)
            k = key.lower()
            if k not in kwargs:
                kwargs[k] = val

    return ticker, kwargs


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reflect command."""
    args = context.args or []
    ticker, kwargs = _parse_reflect_args(args)

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
                lines.append(f'  /reflect {t} plan_followed=yes mistake="..."')
            await update.message.reply_text("\n".join(lines))
        except Exception as exc:
            await update.message.reply_text(f"Error fetching reflections: {exc}")
        return

    # Submit reflection
    plan_followed = kwargs.get("plan_followed", "").lower()
    mistake = kwargs.get("mistake", "")
    system_missed = kwargs.get("system_missed", "")

    if not mistake:
        await update.message.reply_text(
            f"Reflection rejected: main mistake must be non-empty text.\n"
            f'Usage: /reflect {ticker} plan_followed=yes mistake="what I learned" system_missed="optional"'
        )
        return

    if len(mistake) < 10:
        await update.message.reply_text("Reflection too short. What did you learn from this trade? (min 10 chars)")
        return

    # Find the trade
    trades = db.get_recent_trades(ticker=ticker, limit=5)
    sell_trades = [t for t in trades if t.get("side") == "SELL" and not t.get("reflection_completed")]

    if not sell_trades:
        await update.message.reply_text(f"No unreflected exit trades found for {ticker}.")
        return

    trade = sell_trades[0]
    trade_id = trade["id"]

    # Save reflection by updating the trade
    try:
        db.get_client().table("trades").update({
            "reflection_completed": True,
            "notes": f"Reflection: plan_followed={plan_followed}, mistake={mistake}, system_missed={system_missed}",
        }).eq("id", trade_id).execute()

        needs_review = any(kw in mistake.lower() for kw in ["rule", "change", "add rule", "ban", "threshold"])

        lines = [
            f"Reflection saved for {ticker} trade.",
            f"Plan followed: {plan_followed or 'not specified'}.",
            f"Rules review flag: {needs_review}.",
            "This reflection will appear in the next weekly audit snapshot.",
        ]
        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("Failed to save reflection: %s", exc)
        await update.message.reply_text(f"Error saving reflection: {exc}")
