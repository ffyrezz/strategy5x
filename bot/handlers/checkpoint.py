"""
/checkpoint — Month 3 decision report.

Generates a comprehensive verdict on system effectiveness:
CONTINUE / SIMPLIFY / PAUSE based on calibration, decision quality,
and engagement metrics.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _compute_weekly_metrics(weeks_back: int = 8) -> list[dict[str, Any]]:
    """Compute per-week metrics for trend analysis."""
    now = now_utc()
    weekly = []

    for w in range(weeks_back):
        end = now - timedelta(weeks=w)
        start = end - timedelta(weeks=1)

        trades = db.get_trades_since(start.isoformat())
        trades = [t for t in trades if t.get("filled_at", "") <= end.isoformat()]

        sells = [t for t in trades if t.get("side") == "SELL"]
        scoring = db.get_scoring_runs_since(start.isoformat())

        # Plan adherence rate
        with_plan = [t for t in sells if t.get("plan_adherence") == "followed"]
        plan_rate = len(with_plan) / len(sells) if sells else None

        # Reflection rate
        reflected = [t for t in sells if t.get("reflection_completed")]
        refl_rate = len(reflected) / len(sells) if sells else None

        # Non-override rate
        if scoring:
            non_or = [r for r in scoring if not r.get("da_override")]
            no_rate = len(non_or) / len(scoring)
        else:
            no_rate = None

        # Decision quality
        dqs = None
        if plan_rate is not None and refl_rate is not None and no_rate is not None:
            dqs = round(100 * (0.5 * plan_rate + 0.3 * refl_rate + 0.2 * no_rate), 1)

        weekly.append({
            "week_end": end.strftime("%Y-%m-%d"),
            "trades": len(trades),
            "sells": len(sells),
            "plan_rate": plan_rate,
            "refl_rate": refl_rate,
            "dqs": dqs,
        })

    return list(reversed(weekly))


def _detect_trend(values: list[float | None], window: int = 3) -> str:
    """Detect if recent values are trending up, down, or flat."""
    valid = [v for v in values[-window:] if v is not None]
    if len(valid) < 2:
        return "insufficient_data"
    diffs = [valid[i] - valid[i - 1] for i in range(1, len(valid))]
    if all(d < -1 for d in diffs):
        return "declining"
    if all(d > 1 for d in diffs):
        return "improving"
    return "stable"


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /checkpoint command."""
    try:
        now = now_utc()
        all_trades = db.get_all_trades()
        total_trades = len(all_trades)
        sells = [t for t in all_trades if t.get("side") == "SELL"]

        # With plans vs without
        with_plan = [t for t in sells if t.get("precommitment_plan_id")]
        without_plan = [t for t in sells if not t.get("precommitment_plan_id")]

        # Weekly trend data
        weekly = _compute_weekly_metrics(weeks_back=8)

        # Current metrics (30-day)
        month_ago = (now - timedelta(days=30)).isoformat()
        month_trades = db.get_trades_since(month_ago)
        month_sells = [t for t in month_trades if t.get("side") == "SELL"]
        month_scoring = db.get_scoring_runs_since(month_ago)

        # Calibration
        calibration = None
        run_lookup = {r["id"]: r for r in month_scoring}
        scored = []
        for t in month_sells:
            run_id = t.get("scoring_run_id")
            if run_id and run_id in run_lookup:
                run = run_lookup[run_id]
                comp = run.get("composite_score")
                pnl = t.get("realized_pnl_pct")
                if comp is not None and pnl is not None:
                    scored.append((float(comp), float(pnl)))
        if len(scored) >= 5:
            errors = [((c / 80.0) - (1.0 if p > 0 else 0.0)) ** 2 for c, p in scored]
            calibration = round(100 - 100 * sum(errors) / len(errors), 1)

        # Current DQS
        if month_sells:
            plan_r = len([t for t in month_sells if t.get("plan_adherence") == "followed"]) / len(month_sells)
            refl_r = len([t for t in month_sells if t.get("reflection_completed")]) / len(month_sells)
            no_r = len([r for r in month_scoring if not r.get("da_override")]) / len(month_scoring) if month_scoring else 1.0
            dqs = round(100 * (0.5 * plan_r + 0.3 * refl_r + 0.2 * no_r), 1)
        else:
            dqs = None

        # False negatives
        fn_candidates = db.get_rejected_candidates_for_tracking()
        fn_count = sum(
            1 for c in fn_candidates
            if c.get("false_negative_peak_price") and c.get("false_negative_price_at_rejection")
            and float(c.get("false_negative_price_at_rejection", 0)) > 0
            and ((float(c["false_negative_peak_price"]) - float(c["false_negative_price_at_rejection"])) /
                 float(c["false_negative_price_at_rejection"]) * 100) > 25
        )

        # Trend analysis
        dqs_trend = _detect_trend([w.get("dqs") for w in weekly])

        # Check for abandoned system
        recent_trades = db.get_trades_since((now - timedelta(days=14)).isoformat())
        abandoned = len(recent_trades) == 0 and total_trades > 0

        # Determine verdict
        if abandoned:
            verdict = "PAUSE"
            verdict_reason = "No trades logged for 2+ weeks"
        elif dqs_trend == "declining":
            verdict = "SIMPLIFY"
            verdict_reason = "Decision Quality declining for 3+ weeks"
        elif calibration is not None and calibration > 55 and dqs is not None and dqs > 70:
            verdict = "CONTINUE"
            verdict_reason = f"Calibration {calibration} > 55, DQS {dqs} > 70"
        elif total_trades < 5:
            verdict = "CONTINUE"
            verdict_reason = "Insufficient data for definitive assessment"
        else:
            verdict = "CONTINUE"
            verdict_reason = "Metrics within acceptable range"

        # Format report
        lines = [
            "MONTH 3 DECISION CHECKPOINT",
            "",
            f"Total trades: {total_trades} ({len(sells)} exits)",
            f"  With plans: {len(with_plan)} | Without: {len(without_plan)}",
            "",
            f"Calibration (30d): {calibration if calibration is not None else 'N/A (need 5+ exits)'}",
            f"Decision Quality (30d): {dqs if dqs is not None else 'N/A'}",
            f"DQS trend: {dqs_trend}",
            f"False negatives (30d): {fn_count}",
            "",
        ]

        # Weekly trend table
        lines.append("WEEKLY TREND:")
        for w in weekly[-4:]:
            d = w.get("dqs")
            d_str = f"{d:.0f}" if d is not None else "-"
            lines.append(f"  {w['week_end']}: {w['trades']} trades, DQS {d_str}")

        lines.append("")
        lines.append(f"VERDICT: {verdict}")
        lines.append(f"Reason: {verdict_reason}")

        if verdict == "PAUSE":
            lines.append("\nAction: Re-engage or formally wind down. Data export recommended: /export")
        elif verdict == "SIMPLIFY":
            lines.append("\nAction: Review which features are actually being used. Disable unused complexity.")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("Checkpoint failed: %s", exc, exc_info=True)
        await update.message.reply_text(f"Checkpoint generation failed: {exc}")
