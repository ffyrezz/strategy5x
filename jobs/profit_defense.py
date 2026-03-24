"""
Scheduled job: Profit defense and stop-loss enforcement.

Runs every hour during US market hours.
Alerts on:
  - >= 40% gain from avg_cost: CRITICAL trim alert
  - >= 25% gain from avg_cost: HIGH trim alert
  - <= -25% loss from avg_cost: STOP WARNING (approaching F2)
  - <= -35% loss from avg_cost: F2 BREACH — mandatory exit
"""

from __future__ import annotations

import logging
import math

import db
from data.market_data import get_extended_hours_price
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

# Thresholds: (pct_threshold, dedupe_suffix, priority, is_loss)
GAIN_THRESHOLDS = [
    (40.0, "40", "critical", False),
    (25.0, "25", "high", False),
]
LOSS_THRESHOLDS = [
    (-35.0, "f2_breach", "critical", True),
    (-25.0, "stop_warn", "high", True),
]


def _already_alerted_today(dedupe_key: str) -> bool:
    """Check if an alert with this dedupe_key already exists."""
    try:
        resp = (
            db.get_client()
            .table("alerts")
            .select("id")
            .eq("dedupe_key", dedupe_key)
            .limit(1)
            .execute()
        )
        return bool(resp.data)
    except Exception:
        return False


def _format_gain_alert(
    ticker: str, gain_pct: float, last_price: float, avg_cost: float,
    qty: float, unrealized_pnl: float, plan_action: str, threshold: float,
) -> str:
    """Format a profit defense trim alert."""
    half_qty = math.ceil(qty / 2)
    return (
        f"TRIM ALERT: {ticker} is +{gain_pct:.1f}% from your avg cost\n"
        f"Price: ${last_price:.2f} | Avg: ${avg_cost:.2f}\n"
        f"Position: {int(qty)} shares | Gain: ${unrealized_pnl:.2f}\n\n"
        f"Your pre-committed plan says: {plan_action}\n\n"
        f"Action required: Type /trade {ticker} SELL {half_qty} {last_price:.2f}\n"
        f"Or type /ack profit_defense_{ticker} to hold with reason"
    )


def _format_stop_warning(
    ticker: str, gain_pct: float, last_price: float, avg_cost: float,
    qty: float, unrealized_pnl: float,
) -> str:
    """Format a stop-loss warning."""
    return (
        f"STOP WARNING: {ticker} is {gain_pct:.1f}% from your avg cost\n"
        f"Price: ${last_price:.2f} | Avg: ${avg_cost:.2f}\n"
        f"Position: {int(qty)} shares | Loss: ${unrealized_pnl:.2f}\n\n"
        f"Approaching F2 mandatory exit at -35%.\n"
        f"Review position and decide: /trade {ticker} SELL or hold"
    )


def _format_f2_breach(
    ticker: str, gain_pct: float, last_price: float, avg_cost: float,
    qty: float, unrealized_pnl: float,
) -> str:
    """Format an F2 breach mandatory exit alert."""
    return (
        f"F2 BREACH: {ticker} is {gain_pct:.1f}% from your avg cost\n"
        f"Price: ${last_price:.2f} | Avg: ${avg_cost:.2f}\n"
        f"Position: {int(qty)} shares | Loss: ${unrealized_pnl:.2f}\n\n"
        f"MANDATORY EXIT required within 30 minutes of market open.\n"
        f"Action required: /trade {ticker} SELL {int(qty)} {last_price:.2f}"
    )


async def run() -> None:
    """Check all positions for profit defense and stop-loss thresholds."""
    logger.info("Profit defense job starting")

    try:
        positions = db.get_active_positions()
        if not positions:
            return

        date_str = now_utc().strftime("%Y%m%d")

        for pos in positions:
            ticker = pos["ticker"]
            avg_cost = float(pos.get("avg_cost", 0))
            qty = float(pos.get("quantity", 0))

            if avg_cost <= 0 or qty <= 0:
                continue

            try:
                ext = get_extended_hours_price(ticker)
                last_price = ext.get("price")
                if not last_price:
                    continue

                gain_pct = ((last_price - avg_cost) / avg_cost) * 100
                unrealized_pnl = qty * (last_price - avg_cost)

                # Check gain thresholds (highest first)
                if gain_pct >= 25:
                    # Get plan for context
                    plan = db.get_active_plan(ticker)
                    plan_action = "No plan logged"
                    if plan:
                        bull = plan.get("if_approval")
                        if isinstance(bull, dict):
                            plan_action = bull.get("action", "No action specified")
                        elif isinstance(bull, str):
                            plan_action = bull

                    for threshold, suffix, priority, _ in GAIN_THRESHOLDS:
                        if gain_pct >= threshold:
                            dedupe_key = f"profit_defense_{ticker}_{date_str}_{suffix}"
                            if _already_alerted_today(dedupe_key):
                                continue

                            message = _format_gain_alert(
                                ticker, gain_pct, last_price, avg_cost,
                                qty, unrealized_pnl, plan_action, threshold,
                            )
                            alert_row = {
                                "alert_type": "price_move",
                                "priority": priority,
                                "ticker": ticker,
                                "position_id": pos.get("id"),
                                "title": f"{ticker} +{gain_pct:.1f}% — trim alert",
                                "body": message,
                                "action_required": True,
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
                                    logger.info("Profit defense alert sent: %s +%.1f%%", ticker, gain_pct)
                            except Exception:
                                logger.debug("Profit defense deduped: %s", dedupe_key)
                            break  # Only alert at highest threshold

                # Check loss thresholds (lowest first)
                if gain_pct <= -25:
                    for threshold, suffix, priority, _ in LOSS_THRESHOLDS:
                        if gain_pct <= threshold:
                            dedupe_key = f"profit_defense_{ticker}_{date_str}_{suffix}"
                            if _already_alerted_today(dedupe_key):
                                continue

                            if threshold == -35.0:
                                message = _format_f2_breach(
                                    ticker, gain_pct, last_price, avg_cost,
                                    qty, unrealized_pnl,
                                )
                            else:
                                message = _format_stop_warning(
                                    ticker, gain_pct, last_price, avg_cost,
                                    qty, unrealized_pnl,
                                )

                            alert_row = {
                                "alert_type": "price_move",
                                "priority": priority,
                                "ticker": ticker,
                                "position_id": pos.get("id"),
                                "title": f"{ticker} {gain_pct:.1f}% — {suffix.replace('_', ' ')}",
                                "body": message,
                                "action_required": True,
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
                                    logger.info("Stop-loss alert sent: %s %.1f%%", ticker, gain_pct)
                            except Exception:
                                logger.debug("Stop-loss deduped: %s", dedupe_key)
                            break  # Only alert at worst threshold

            except Exception as exc:
                logger.warning("Profit defense check failed for %s: %s", ticker, exc)

    except Exception as exc:
        logger.error("Profit defense job failed: %s", exc, exc_info=True)
        db.log_error_alert("profit_defense", str(exc))


def main():
    """Entry point for GitHub Actions: python -m jobs.profit_defense"""
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
