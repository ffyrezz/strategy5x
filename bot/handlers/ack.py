"""
/ack ALERT_ID [optional note] — Acknowledge an alert.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc, format_sgt

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ack command."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /ack ALERT_ID [optional note]")
        return

    alert_id = args[0]
    note = " ".join(args[1:]) if len(args) > 1 else None

    # Look up alert
    alert = db.get_alert(alert_id)
    if not alert:
        await update.message.reply_text("Alert not found or already closed.")
        return

    # Check if already acknowledged
    if alert.get("acknowledged_at"):
        ack_time = alert["acknowledged_at"]
        await update.message.reply_text(f"Alert already acknowledged at {ack_time}.")
        return

    # Acknowledge
    now = now_utc()
    updates = {
        "acknowledged_at": now.isoformat(),
        "delivery_status": "acknowledged",
    }
    if note:
        updates["user_response"] = note

    try:
        db.update_alert(alert_id, updates)
    except Exception as exc:
        await update.message.reply_text(f"Error acknowledging alert: {exc}")
        return

    lines = [f"Acknowledged: {alert_id}."]

    # Check for linked plan
    ticker = alert.get("ticker")
    if ticker:
        plan = db.get_active_plan(ticker)
        if plan:
            lines.append(f"Linked plan: {plan.get('id', '?')[:20]}... is active.")
        else:
            lines.append(f"⚠️ No active plan for {ticker}.")

    lines.append("No further reply needed unless execution deviates.")

    await update.message.reply_text("\n".join(lines))
