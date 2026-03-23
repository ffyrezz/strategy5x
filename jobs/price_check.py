"""
Scheduled job: Check price movements on open positions.

Runs every 10 minutes during US market hours.
Alerts on >10% move from previous close.
"""

from __future__ import annotations

import logging

import config
import db
from data.market_data import get_price_data
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


async def run() -> None:
    """Check prices for all open positions."""
    logger.info("Price check job starting")

    try:
        positions = db.get_active_positions()
        if not positions:
            return

        for pos in positions:
            ticker = pos["ticker"]
            try:
                price_data = get_price_data(ticker)
                current = price_data.get("price")
                prev_close = price_data.get("previous_close")

                if not current or not prev_close:
                    continue

                change_pct = ((current - prev_close) / prev_close) * 100

                if abs(change_pct) >= config.PRICE_MOVE_THRESHOLD_PCT:
                    direction = "📈" if change_pct > 0 else "📉"
                    dedupe_key = f"price_move_{ticker}_{now_utc().strftime('%Y%m%d')}_{int(abs(change_pct))}"

                    # Get plan for context
                    plan = db.get_active_plan(ticker)
                    plan_note = ""
                    if plan:
                        if change_pct < -config.PRICE_MOVE_THRESHOLD_PCT:
                            bear = plan.get("if_rejection")
                            if isinstance(bear, dict):
                                plan_note = f"\nPlan (bear): {bear.get('action', '?')}"
                        else:
                            bull = plan.get("if_approval")
                            if isinstance(bull, dict):
                                plan_note = f"\nPlan (bull): {bull.get('action', '?')}"

                    qty = pos.get("quantity", "?")
                    avg = pos.get("avg_cost", "?")

                    message = (
                        f"{direction} {ticker} moved {change_pct:+.1f}%\n"
                        f"Price: ${current:.2f} (prev close: ${prev_close:.2f})\n"
                        f"Position: {qty} sh @ ${avg}"
                        f"{plan_note}"
                    )

                    # Insert alert (dedupe prevents duplicates)
                    alert_row = {
                        "alert_type": "price_move",
                        "priority": "high",
                        "ticker": ticker,
                        "position_id": pos.get("id"),
                        "title": f"{ticker} {change_pct:+.1f}% move",
                        "body": message,
                        "action_required": abs(change_pct) >= 15,
                        "channel": "telegram",
                        "delivery_status": "queued",
                        "delivery_attempts": 0,
                        "dedupe_key": dedupe_key,
                        "created_at": now_utc().isoformat(),
                    }

                    try:
                        saved = db.insert_alert(alert_row)
                        sent = await send_telegram(message)
                        if sent:
                            db.update_alert(saved.get("id", ""), {
                                "delivery_status": "sent",
                                "sent_at": now_utc().isoformat(),
                            })
                            logger.info("Price alert sent: %s %+.1f%%", ticker, change_pct)
                    except Exception:
                        # Deduped — already alerted today for similar magnitude
                        pass

            except Exception as exc:
                logger.warning("Price check failed for %s: %s", ticker, exc)

    except Exception as exc:
        logger.error("Price check job failed: %s", exc, exc_info=True)
        db.log_error_alert("price_check", str(exc))
