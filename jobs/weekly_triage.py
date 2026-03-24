"""
Scheduled job: Weekly position triage.

Runs Sunday 10:00 PM SGT (14:00 UTC).
Flags each position as GREEN, AMBER, or RED and sends a triage summary.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import db
from data.market_data import get_extended_hours_price
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _days_held(position: dict[str, Any]) -> int:
    """Calculate how many days a position has been held."""
    created = position.get("created_at")
    if not created:
        return 0
    try:
        if isinstance(created, str):
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        else:
            dt = created
        delta = now_utc() - dt
        return max(0, delta.days)
    except Exception:
        return 0


def _get_catalyst_days_away(ticker: str) -> int | None:
    """Return days until the nearest catalyst for this ticker, or None."""
    candidate = db.get_candidate(ticker)
    if not candidate or not candidate.get("catalyst_date"):
        return None
    try:
        cat_str = str(candidate["catalyst_date"])
        cat_date = datetime.fromisoformat(cat_str).date() if "T" in cat_str else datetime.strptime(cat_str, "%Y-%m-%d").date()
        delta = (cat_date - now_utc().date()).days
        return delta
    except Exception:
        return None


def _classify_position(
    pos: dict[str, Any], pnl_pct: float, days: int, cat_days: int | None,
) -> tuple[str, str]:
    """
    Classify position into GREEN/AMBER/RED with a reason.

    GREEN: catalyst within 21 days, OR profitable
    AMBER: held >14 days, no catalyst <14 days, pnl between -15% and 0%
    RED: pnl < -15%, OR no catalyst at all, OR catalyst >30 days away AND losing
    """
    # RED checks first (most urgent)
    if pnl_pct < -15:
        return "RED", f"{pnl_pct:+.1f}% | Down >15%"

    if cat_days is None:
        if pnl_pct < 0:
            return "RED", f"{pnl_pct:+.1f}% | No catalyst found"
        # No catalyst but profitable — amber not red
        if days > 14:
            return "AMBER", f"{pnl_pct:+.1f}% | {days}d held | No catalyst"

    if cat_days is not None and cat_days > 30 and pnl_pct < 0:
        return "RED", f"{pnl_pct:+.1f}% | Catalyst T-{cat_days} (>30d away)"

    # GREEN checks
    if cat_days is not None and cat_days <= 21:
        return "GREEN", f"{pnl_pct:+.1f}% | Catalyst T-{cat_days}"

    if pnl_pct > 0:
        cat_note = f"T-{cat_days}" if cat_days is not None else "no catalyst"
        return "GREEN", f"{pnl_pct:+.1f}% | {cat_note}"

    # AMBER: everything else (held a while, no imminent catalyst, slightly down)
    if days > 14 and (cat_days is None or cat_days > 14):
        return "AMBER", f"{pnl_pct:+.1f}% | {days}d held | No catalyst <14d"

    # Default to AMBER for anything not clearly green or red
    cat_note = f"T-{cat_days}" if cat_days is not None else "no catalyst"
    return "AMBER", f"{pnl_pct:+.1f}% | {days}d held | {cat_note}"


def _format_triage_message(
    greens: list[tuple[str, str]],
    ambers: list[tuple[str, str]],
    reds: list[tuple[str, str]],
    total_mv: float,
    total_pnl: float,
) -> str:
    """Format the weekly triage report."""
    now = now_utc()
    total_positions = len(greens) + len(ambers) + len(reds)
    lines = [
        f"WEEKLY TRIAGE — {now.strftime('%Y-%m-%d')}",
        f"{total_positions} positions | ${total_mv:,.0f} MV | ${total_pnl:+,.0f} P&L",
        "",
    ]

    if greens:
        lines.append("GREEN:")
        for ticker, detail in greens:
            lines.append(f"  {ticker}: {detail} | HOLD")

    if ambers:
        if greens:
            lines.append("")
        lines.append("AMBER (requires /hold TICKER or /exit TICKER):")
        for ticker, detail in ambers:
            lines.append(f"  {ticker}: {detail}")

    if reds:
        if greens or ambers:
            lines.append("")
        lines.append("RED (requires immediate decision):")
        for ticker, detail in reds:
            lines.append(f"  {ticker}: {detail} | EXIT or justify")

    lines.append("")
    lines.append("Reply with:")
    lines.append("/hold TICKER reason — to keep position")
    lines.append("/trade TICKER SELL qty price — to exit")
    lines.append("Silence = you accept the triage recommendation")

    return "\n".join(lines)


async def run() -> None:
    """Generate and send the weekly position triage."""
    logger.info("Weekly triage starting")

    try:
        positions = db.get_active_positions()
        if not positions:
            logger.info("No positions to triage")
            return

        greens: list[tuple[str, str]] = []
        ambers: list[tuple[str, str]] = []
        reds: list[tuple[str, str]] = []
        total_mv = 0.0
        total_pnl = 0.0

        for pos in positions:
            ticker = pos["ticker"]
            avg_cost = float(pos.get("avg_cost", 0))
            qty = float(pos.get("quantity", 0))

            # Get fresh price
            try:
                ext = get_extended_hours_price(ticker)
                last_price = ext.get("price") or float(pos.get("last_price", 0))
            except Exception:
                last_price = float(pos.get("last_price", 0))

            if avg_cost <= 0 or qty <= 0:
                continue

            mv = qty * last_price if last_price else 0
            pnl = qty * (last_price - avg_cost) if last_price else 0
            pnl_pct = ((last_price - avg_cost) / avg_cost) * 100 if last_price and avg_cost > 0 else 0

            total_mv += mv
            total_pnl += pnl

            days = _days_held(pos)
            cat_days = _get_catalyst_days_away(ticker)

            flag, detail = _classify_position(pos, pnl_pct, days, cat_days)

            if flag == "GREEN":
                greens.append((ticker, detail))
            elif flag == "AMBER":
                ambers.append((ticker, detail))
            else:
                reds.append((ticker, detail))

        message = _format_triage_message(greens, ambers, reds, total_mv, total_pnl)

        sent = await send_telegram(message)

        # Log as alert
        priority = "critical" if reds else "high" if ambers else "normal"
        db.insert_alert({
            "alert_type": "heartbeat",
            "priority": priority,
            "title": "Weekly Position Triage",
            "body": message[:500],
            "action_required": bool(reds or ambers),
            "channel": "telegram",
            "delivery_status": "sent" if sent else "failed",
            "delivery_attempts": 1,
            "sent_at": now_utc().isoformat() if sent else None,
            "dedupe_key": f"weekly_triage_{now_utc().strftime('%Y_%W')}",
            "created_at": now_utc().isoformat(),
        })

        logger.info(
            "Weekly triage %s: %d green, %d amber, %d red",
            "sent" if sent else "FAILED", len(greens), len(ambers), len(reds),
        )

    except Exception as exc:
        logger.error("Weekly triage failed: %s", exc, exc_info=True)
        db.log_error_alert("weekly_triage", str(exc))


def main():
    """Entry point for GitHub Actions: python -m jobs.weekly_triage"""
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
