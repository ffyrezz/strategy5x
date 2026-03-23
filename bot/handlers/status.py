"""
/status command — Show system health and portfolio summary.
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_sgt

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    lines = []

    # System heartbeat
    try:
        db.keepalive_ping()
        lines.append("System: healthy.")
    except Exception:
        lines.append("System: database unreachable.")
        await update.message.reply_text("\n".join(lines))
        return

    # Broker sync freshness
    try:
        positions = db.get_active_positions()
        if positions:
            freshest = max(
                (p.get("source_fresh_at") for p in positions if p.get("source_fresh_at")),
                default=None,
            )
            if freshest:
                lines.append(f"Positions sync: {freshest}.")
            else:
                lines.append("Positions sync: no timestamp available.")
            lines.append(f"Open positions: {len(positions)}.")
        else:
            lines.append("Status partial: no successful position sync recorded yet.")
    except Exception as exc:
        lines.append(f"Position check failed: {exc}")

    # Pending alerts
    try:
        pending = db.get_pending_alerts()
        critical = [a for a in pending if a.get("priority") == "critical"]
        lines.append(f"Pending critical alerts: {len(critical)}.")
    except Exception:
        lines.append("Alert check failed.")

    # Plans coverage
    try:
        upcoming = db.get_upcoming_catalysts(within_days=14)
        missing_plans = []
        for cat in upcoming:
            plan = db.get_active_plan(cat["ticker"])
            if not plan:
                missing_plans.append(cat["ticker"])
        if missing_plans:
            lines.append(f"Open positions lacking active plan: {len(missing_plans)}.")
        else:
            lines.append("All upcoming catalysts have plans.")
    except Exception:
        lines.append("Plan coverage check failed.")

    lines.append("Last weekly audit snapshot: not yet generated.")

    await update.message.reply_text("\n".join(lines))
