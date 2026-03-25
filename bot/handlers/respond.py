"""
/did TICKER ACTION [note] — Log what you actually did in response to system advice.

This is the user's side of the decision audit trail. It closes the feedback loop
by recording what the user did (or chose not to do) after the system advised.

Usage:
  /did KPTI sold 100 shares at 5.94           — logged a sell action
  /did VIR held holding for AAN catalyst       — logged that you chose to hold
  /did WVE exited thesis broken                — logged an exit
  /did ZBIO skipped agreed with DA block       — logged that you skipped
  /did RYTM trimmed sold 25 at 85              — logged a trim
  /did TVTX bought 40 shares at 27.50          — logged a buy
  /did KPTI ignored plan says hold, I disagree — logged an override/ignore

The command finds the most recent pending decision_log entry for that ticker
and marks it with the user's response.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

# Map user action words to standardized responses
ACTION_MAP = {
    "sold": ("followed", "sell"),
    "sell": ("followed", "sell"),
    "bought": ("followed", "buy"),
    "buy": ("followed", "buy"),
    "held": ("followed", "hold"),
    "hold": ("followed", "hold"),
    "holding": ("followed", "hold"),
    "trimmed": ("followed", "trim"),
    "trim": ("followed", "trim"),
    "exited": ("followed", "exit_all"),
    "exit": ("followed", "exit_all"),
    "skipped": ("followed", "block"),
    "skip": ("followed", "block"),
    "ignored": ("ignored", None),
    "ignore": ("ignored", None),
    "overrode": ("overrode", None),
    "override": ("overrode", None),
}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /did TICKER ACTION [note]."""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /did TICKER ACTION [note]\n\n"
            "Actions: sold, bought, held, trimmed, exited, skipped, ignored, overrode\n\n"
            "Examples:\n"
            "  /did VIR held waiting for catalyst\n"
            "  /did RYTM trimmed sold 25 at 85\n"
            "  /did WVE exited thesis broken\n"
            "  /did KPTI ignored plan says hold but I disagree"
        )
        return

    ticker = args[0].upper()
    action_word = args[1].lower()
    note = " ".join(args[2:]) if len(args) > 2 else ""

    # Map the action word
    if action_word not in ACTION_MAP:
        await update.message.reply_text(
            f"Unknown action: {action_word}\n"
            f"Use one of: sold, bought, held, trimmed, exited, skipped, ignored, overrode"
        )
        return

    user_response, mapped_action = ACTION_MAP[action_word]

    # Find the most recent pending decision for this ticker
    pending = db.get_decisions(ticker=ticker, limit=10)
    target = None
    for d in pending:
        if d.get("user_response") == "pending":
            target = d
            break

    now = now_utc()

    if target:
        # Update the existing decision log entry
        updates = {
            "user_response": user_response,
            "user_response_detail": f"{action_word} {note}".strip(),
            "user_responded_at": now.isoformat(),
        }
        db.update_decision(target["id"], updates)

        event_type = target.get("event_type", "?")
        advice = target.get("advice_summary", "?")

        lines = [
            f"Logged: {ticker} — {action_word} {note}".strip(),
            f"Linked to: {event_type}",
            f"System advised: {advice[:100]}",
            f"Your response: {user_response}",
        ]
    else:
        # No pending decision found — create a standalone user_action entry
        db.log_decision(
            event_type="user_action",
            ticker=ticker,
            source="user_manual",
            advice_summary=f"User reported: {action_word} {note}".strip(),
            advice_action=mapped_action,
            user_response="no_response_required",
        )

        lines = [
            f"Logged: {ticker} — {action_word} {note}".strip(),
            f"No pending system advice found for {ticker}.",
            f"Recorded as standalone action.",
        ]

    # Show count of remaining pending decisions for this ticker
    remaining = sum(1 for d in pending if d.get("user_response") == "pending" and d.get("id") != (target or {}).get("id"))
    if remaining > 0:
        lines.append(f"{remaining} more pending decision(s) for {ticker}.")

    await update.message.reply_text("\n".join(lines))
