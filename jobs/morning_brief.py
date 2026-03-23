"""
Scheduled job: Generate and send morning brief.

Runs at 8:00 AM SGT on weekdays.
Queries positions, catalysts, and missing artifacts, then sends via Telegram.
"""

from __future__ import annotations

import logging

import config
import db
from bot.formatters import format_morning_brief
from data.market_data import get_bulk_prices
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


async def run() -> None:
    """Generate and send the morning brief."""
    logger.info("Morning brief job starting")

    try:
        # 1. Fetch positions and refresh prices
        positions = db.get_active_positions()
        if positions:
            tickers = [p["ticker"] for p in positions]
            prices = get_bulk_prices(tickers)

            # Update position prices (in-memory for brief, not persisted here)
            for pos in positions:
                pd = prices.get(pos["ticker"], {})
                if pd.get("price"):
                    pos["last_price"] = pd["price"]
                    qty = float(pos.get("quantity", 0))
                    avg = float(pos.get("avg_cost", 0))
                    pos["market_value"] = qty * pd["price"]
                    if avg > 0:
                        pos["unrealized_pnl"] = qty * (pd["price"] - avg)
                        pos["unrealized_pnl_pct"] = ((pd["price"] - avg) / avg) * 100

        # 2. Fetch upcoming catalysts
        catalysts = db.get_upcoming_catalysts(within_days=14)

        # 3. Find missing artifacts
        missing_plans = []
        missing_scores = []

        for cat in catalysts:
            plan = db.get_active_plan(cat["ticker"])
            if not plan:
                missing_plans.append(cat["ticker"])
            score_run = db.get_latest_scoring_run(cat["ticker"])
            if not score_run:
                missing_scores.append(cat["ticker"])

        # Also check held positions with catalyst dates
        for pos in positions:
            t = pos["ticker"]
            if pos.get("catalyst_date") and t not in missing_plans:
                plan = db.get_active_plan(t)
                if not plan:
                    missing_plans.append(t)

        # 4. Pending acks
        pending = db.get_pending_alerts()

        # 5. Format
        text = format_morning_brief(
            positions=positions,
            catalysts=catalysts,
            missing_plans=list(set(missing_plans)),
            missing_scores=list(set(missing_scores)),
            pending_acks=len(pending),
        )

        # 6. Send
        sent = await send_telegram(text)

        # 7. Log as alert
        db.insert_alert({
            "alert_type": "morning_brief",
            "priority": "normal",
            "title": "Morning Brief",
            "body": text[:500],
            "action_required": False,
            "channel": "telegram",
            "delivery_status": "sent" if sent else "failed",
            "delivery_attempts": 1,
            "sent_at": now_utc().isoformat() if sent else None,
            "dedupe_key": f"morning_brief_{now_utc().strftime('%Y%m%d')}",
            "created_at": now_utc().isoformat(),
        })

        logger.info("Morning brief %s", "sent" if sent else "FAILED")

    except Exception as exc:
        logger.error("Morning brief failed: %s", exc, exc_info=True)
        db.log_error_alert("morning_brief", str(exc))
