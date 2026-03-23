"""
Scheduled job: Check catalyst countdowns and send T-7, T-3, T-1 alerts.

Runs daily at 9:00 PM SGT (before US market open).
For T-1 and T-0: includes pre-commitment plan text in alert.
3 AM format: max 5 lines, plan first, single action.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

import config
import db
from bot.formatters import format_catalyst_alert_3am
from data.catalyst_calendar import days_until_catalyst, format_countdown
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


async def send_telegram(text: str) -> bool:
    """Send alert via Telegram."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        return resp.status_code == 200


async def run() -> None:
    """Check for catalyst alerts at T-7, T-3, T-1."""
    logger.info("Catalyst alerts job starting")

    try:
        today = date.today()

        for t_minus in config.CATALYST_ALERT_DAYS:
            target_date = today + timedelta(days=t_minus)

            # Find candidates with this catalyst date
            candidates = db.get_upcoming_catalysts(within_days=max(config.CATALYST_ALERT_DAYS) + 1)
            matching = [
                c for c in candidates
                if c.get("catalyst_date") and str(c["catalyst_date"]) == str(target_date)
            ]

            for candidate in matching:
                ticker = candidate["ticker"]
                cat_type = candidate.get("catalyst_type", "catalyst")
                countdown = format_countdown(t_minus)

                # Build dedupe key
                dedupe_key = f"catalyst_{ticker}_{target_date}_T{t_minus}"

                # Get plan and position
                plan = db.get_active_plan(ticker)
                position = db.get_position_by_ticker(ticker)

                # Determine priority
                priority = "critical" if t_minus <= 1 else "high" if t_minus <= 3 else "normal"

                # Format message
                alert_id = dedupe_key  # use dedupe_key as a readable alert ref
                message = format_catalyst_alert_3am(
                    ticker=ticker,
                    catalyst_type=cat_type,
                    countdown=countdown,
                    plan=plan,
                    position=position,
                    alert_id=alert_id,
                )

                # Insert alert record
                alert_row = {
                    "alert_type": "catalyst",
                    "priority": priority,
                    "ticker": ticker,
                    "title": f"{ticker} {cat_type} {countdown}",
                    "body": message,
                    "precommitted_plan_summary": _extract_plan_summary(plan) if plan else None,
                    "action_required": t_minus <= 3,
                    "channel": "telegram",
                    "delivery_status": "queued",
                    "delivery_attempts": 0,
                    "dedupe_key": dedupe_key,
                    "created_at": now_utc().isoformat(),
                }

                try:
                    saved_alert = db.insert_alert(alert_row)
                except Exception:
                    # Deduped — already sent today
                    logger.info("Alert deduped: %s", dedupe_key)
                    continue

                # Send via Telegram
                sent = await send_telegram(message)
                if sent:
                    db.update_alert(saved_alert.get("id", ""), {
                        "delivery_status": "sent",
                        "sent_at": now_utc().isoformat(),
                    })
                    logger.info("Sent catalyst alert: %s %s", ticker, countdown)
                else:
                    logger.error("Failed to send catalyst alert: %s", ticker)

    except Exception as exc:
        logger.error("Catalyst alerts job failed: %s", exc, exc_info=True)
        db.log_error_alert("catalyst_alerts", str(exc))


def _extract_plan_summary(plan: dict) -> str:
    """Extract a brief plan summary for the alert."""
    parts = []
    for key, label in [("if_approval", "Approval"), ("if_rejection", "CRL"), ("if_mixed", "Mixed")]:
        val = plan.get(key)
        if isinstance(val, dict):
            parts.append(f"{label}: {val.get('action', '?')}")
        elif isinstance(val, str):
            parts.append(f"{label}: {val}")
    return " | ".join(parts)
