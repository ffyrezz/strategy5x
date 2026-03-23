"""
/brief command — Morning brief (portfolio + catalysts + action items).

This is the MOST IMPORTANT handler. The morning brief is the system's
primary visible output and the user's daily starting point.
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import db
from bot.formatters import format_morning_brief
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /brief command. Generate and send morning brief."""
    try:
        # 1. Fetch positions
        positions = db.get_active_positions()

        # 2. Fetch upcoming catalysts (next 14 days)
        catalysts = db.get_upcoming_catalysts(within_days=14)

        # 3. Determine missing artifacts
        missing_plans = []
        missing_scores = []
        for cat in catalysts:
            plan = db.get_active_plan(cat["ticker"])
            if not plan:
                missing_plans.append(cat["ticker"])
            score = db.get_latest_scoring_run(cat["ticker"])
            if not score:
                missing_scores.append(cat["ticker"])

        # Also check positions with catalysts but no plans
        for pos in positions:
            if pos.get("catalyst_date") and pos["ticker"] not in missing_plans:
                plan = db.get_active_plan(pos["ticker"])
                if not plan:
                    missing_plans.append(pos["ticker"])

        # 4. Count pending acks
        pending = db.get_pending_alerts()
        pending_acks = len(pending)

        # 5. Format the brief
        text = format_morning_brief(
            positions=positions,
            catalysts=catalysts,
            missing_plans=list(set(missing_plans)),
            missing_scores=list(set(missing_scores)),
            pending_acks=pending_acks,
        )

        # 6. Log as alert
        try:
            db.insert_alert({
                "alert_type": "morning_brief",
                "priority": "normal",
                "title": "Morning Brief",
                "body": text[:500],
                "action_required": False,
                "channel": "telegram",
                "delivery_status": "sent",
                "sent_at": now_utc().isoformat(),
                "dedupe_key": f"morning_brief_{now_utc().strftime('%Y%m%d')}",
                "created_at": now_utc().isoformat(),
            })
        except Exception as exc:
            logger.warning("Failed to log morning brief alert: %s", exc)

        await update.message.reply_text(text)

    except Exception as exc:
        logger.error("Brief generation failed: %s", exc, exc_info=True)
        await update.message.reply_text(f"⚠️ Brief generation failed: {exc}")
