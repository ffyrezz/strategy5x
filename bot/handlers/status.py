"""
/status command — Show system health, portfolio summary, and growth metrics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _freshness_icon(fresh_at: str | None) -> str:
    """Return freshness indicator based on age."""
    if not fresh_at:
        return "🔴"
    try:
        if isinstance(fresh_at, str):
            dt = datetime.fromisoformat(fresh_at.replace("Z", "+00:00"))
        else:
            dt = fresh_at
        age_hours = (now_utc() - dt).total_seconds() / 3600
        if age_hours < 1:
            return "🟢"
        if age_hours < 6:
            return "🟡"
        return "🔴"
    except Exception:
        return "🔴"


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    lines = []

    # System health
    try:
        db.keepalive_ping()
        lines.append("System: 🟢 healthy")
    except Exception:
        lines.append("System: 🔴 database unreachable")
        await update.message.reply_text("\n".join(lines))
        return

    # Portfolio summary
    try:
        positions = db.get_active_positions()
        total_value = sum(float(p.get("market_value") or 0) for p in positions)
        total_pnl = sum(float(p.get("unrealized_pnl") or 0) for p in positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Portfolio: ${total_value:,.0f} ({pnl_sign}${total_pnl:,.0f})")
        lines.append(f"Positions: {len(positions)}")
    except Exception as exc:
        positions = []
        lines.append(f"Portfolio: error ({exc})")

    # Position sync freshness
    try:
        fresh_at = db.get_latest_position_freshness()
        icon = _freshness_icon(fresh_at)
        if fresh_at:
            lines.append(f"Last sync: {icon} {str(fresh_at)[:19]}")
        else:
            lines.append(f"Last sync: {icon} no sync recorded")
    except Exception:
        lines.append("Last sync: 🔴 unknown")

    # Upcoming catalysts
    try:
        catalysts = db.get_upcoming_catalysts(within_days=7)
        if catalysts:
            cat_str = ", ".join(f"{c['ticker']}({c.get('catalyst_date', '?')})" for c in catalysts[:4])
            lines.append(f"Catalysts (7d): {len(catalysts)} — {cat_str}")
        else:
            lines.append("Catalysts (7d): none")
    except Exception:
        lines.append("Catalysts: check failed")

    # Missing plans
    try:
        missing = db.get_positions_missing_plans(within_days=7)
        if missing:
            tickers = ", ".join(p["ticker"] for p in missing[:3])
            lines.append(f"Missing plans: {len(missing)} ({tickers})")
        else:
            lines.append("Missing plans: 0")
    except Exception:
        lines.append("Missing plans: check failed")

    # Pending reflections
    try:
        stale = db.get_stale_reflection_count(hours=48)
        lines.append(f"Pending reflections (>48h): {stale}")
    except Exception:
        lines.append("Pending reflections: check failed")

    # Unacked alerts
    try:
        unacked = db.get_unacked_alerts_count(hours=24)
        lines.append(f"Unacked alerts (>24h): {unacked}")
    except Exception:
        lines.append("Unacked alerts: check failed")

    # Growth metrics
    try:
        month_ago = (now_utc() - timedelta(days=30)).isoformat()
        trades = db.get_trades_since(month_ago)
        sell_trades = [t for t in trades if t.get("side") == "SELL"]

        if len(sell_trades) >= 5:
            scoring_runs = db.get_scoring_runs_since(month_ago)
            run_lookup = {r["id"]: r for r in scoring_runs}

            # Calibration
            scored = []
            for t in sell_trades:
                run_id = t.get("scoring_run_id")
                if run_id and run_id in run_lookup:
                    run = run_lookup[run_id]
                    comp = run.get("composite_score")
                    pnl = t.get("realized_pnl_pct")
                    if comp is not None and pnl is not None:
                        scored.append((float(comp), float(pnl)))

            if len(scored) >= 5:
                errors = [((c / 80.0) - (1.0 if p > 0 else 0.0)) ** 2 for c, p in scored]
                cal = round(100 - 100 * sum(errors) / len(errors), 1)
                lines.append(f"Calibration (30d): {cal}")

            # Decision quality
            with_plan = [t for t in sell_trades if t.get("plan_adherence") == "followed"]
            reflected = [t for t in sell_trades if t.get("reflection_completed")]
            non_or = [r for r in scoring_runs if not r.get("da_override")]
            plan_rate = len(with_plan) / len(sell_trades)
            refl_rate = len(reflected) / len(sell_trades)
            no_rate = len(non_or) / len(scoring_runs) if scoring_runs else 1.0
            dqs = round(100 * (0.5 * plan_rate + 0.3 * refl_rate + 0.2 * no_rate), 1)
            lines.append(f"Decision Quality (30d): {dqs}")
        else:
            lines.append(f"Growth metrics: need 5+ exits (have {len(sell_trades)})")
    except Exception:
        lines.append("Growth metrics: check failed")

    await update.message.reply_text("\n".join(lines))
