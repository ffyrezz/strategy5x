"""
Weekly Audit Snapshot.

Runs Sunday 10 PM SGT (14:00 UTC) via GitHub Actions.
Computes weekly trading metrics, calibration scores, and decision quality.
Sends summary via Telegram and inserts behavioral_metrics records.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timedelta
from typing import Any

import config
import db
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _compute_calibration_score(trades: list[dict[str, Any]], scoring_runs: list[dict[str, Any]]) -> float | None:
    """
    Calibration Score = 100 - (100 * mean((normalized_score - outcome)^2))

    normalized_score: composite_score / 80 (max possible)
    outcome: 1 if realized_pnl_pct > 0, 0 otherwise

    Returns None if fewer than 5 scored trades.
    """
    # Build scoring run lookup
    run_lookup = {r["id"]: r for r in scoring_runs}

    scored_trades = []
    for t in trades:
        if t.get("side") != "SELL":
            continue
        run_id = t.get("scoring_run_id")
        if not run_id or run_id not in run_lookup:
            continue
        run = run_lookup[run_id]
        composite = run.get("composite_score")
        pnl_pct = t.get("realized_pnl_pct")
        if composite is None or pnl_pct is None:
            continue
        scored_trades.append((float(composite), float(pnl_pct)))

    if len(scored_trades) < 5:
        return None

    errors_sq = []
    for composite, pnl_pct in scored_trades:
        normalized = composite / 80.0
        outcome = 1.0 if pnl_pct > 0 else 0.0
        errors_sq.append((normalized - outcome) ** 2)

    mean_error = sum(errors_sq) / len(errors_sq)
    return round(100 - (100 * mean_error), 1)


def _compute_decision_quality(trades: list[dict[str, Any]], scoring_runs: list[dict[str, Any]]) -> float | None:
    """
    Decision Quality Score = 100 * (0.5 * plan_adherence_rate + 0.3 * reflection_rate + 0.2 * non_override_rate)

    Returns None if no trades.
    """
    if not trades:
        return None

    sell_trades = [t for t in trades if t.get("side") == "SELL"]
    if not sell_trades:
        return None

    # Plan adherence rate
    with_plan = [t for t in sell_trades if t.get("plan_adherence") == "followed"]
    plan_rate = len(with_plan) / len(sell_trades) if sell_trades else 0

    # Reflection rate
    reflected = [t for t in sell_trades if t.get("reflection_completed")]
    reflection_rate = len(reflected) / len(sell_trades) if sell_trades else 0

    # Non-override rate (from scoring runs)
    if scoring_runs:
        non_overrides = [r for r in scoring_runs if not r.get("da_override")]
        non_override_rate = len(non_overrides) / len(scoring_runs)
    else:
        non_override_rate = 1.0

    score = 100 * (0.5 * plan_rate + 0.3 * reflection_rate + 0.2 * non_override_rate)
    return round(score, 1)


def _compute_false_negative_cost(days: int = 30) -> list[dict[str, Any]]:
    """Find rejected candidates that moved >25% in the tracking window."""
    candidates = db.get_rejected_candidates_for_tracking()
    fn_list = []
    for c in candidates:
        peak = c.get("false_negative_peak_price")
        rejection_price = c.get("false_negative_price_at_rejection")
        if peak and rejection_price and float(rejection_price) > 0:
            move_pct = ((float(peak) - float(rejection_price)) / float(rejection_price)) * 100
            if move_pct > config.FALSE_NEGATIVE_THRESHOLD_PCT:
                fn_list.append({
                    "ticker": c["ticker"],
                    "rejection_price": float(rejection_price),
                    "peak_price": float(peak),
                    "move_pct": round(move_pct, 1),
                })
    return fn_list


def _format_audit_message(
    week_trades: list[dict[str, Any]],
    week_scoring: list[dict[str, Any]],
    week_alerts: list[dict[str, Any]],
    week_candidates: list[dict[str, Any]],
    calibration: float | None,
    decision_quality: float | None,
    false_negatives: list[dict[str, Any]],
) -> str:
    """Format the weekly audit snapshot as a Telegram message."""
    now = now_utc()
    lines = [f"WEEKLY AUDIT SNAPSHOT — {now.strftime('%Y-%m-%d')}"]
    lines.append("")

    # Trade metrics
    total_trades = len(week_trades)
    buys = [t for t in week_trades if t.get("side") == "BUY"]
    sells = [t for t in week_trades if t.get("side") == "SELL"]
    with_plan = [t for t in sells if t.get("precommitment_plan_id")]
    without_plan = [t for t in sells if not t.get("precommitment_plan_id")]
    reflected = [t for t in sells if t.get("reflection_completed")]
    pending_reflection = [t for t in sells if not t.get("reflection_completed")]

    lines.append(f"TRADES: {total_trades} ({len(buys)} buys, {len(sells)} sells)")
    if sells:
        lines.append(f"  With plan: {len(with_plan)} | Without: {len(without_plan)}")
        lines.append(f"  Reflected: {len(reflected)} | Pending: {len(pending_reflection)}")

    # Pipeline metrics
    lines.append("")
    added = [c for c in week_candidates if c.get("status") == "candidate"]
    promoted = [c for c in week_candidates if c.get("status") in ("scoring", "entry_ready", "deployed")]
    rejected = [c for c in week_candidates if c.get("status") in ("rejected", "eliminated")]
    lines.append(f"PIPELINE: +{len(added)} added, {len(promoted)} promoted, {len(rejected)} rejected")

    # Scoring runs
    lines.append(f"SCORING RUNS: {len(week_scoring)}")

    # Alerts
    total_alerts = len(week_alerts)
    acked = [a for a in week_alerts if a.get("acknowledged_at")]
    lines.append(f"ALERTS: {total_alerts} sent, {len(acked)} acknowledged")

    # Quality scores
    lines.append("")
    if calibration is not None:
        lines.append(f"Calibration Score: {calibration}")
    else:
        lines.append("Calibration Score: N/A (need 5+ scored exits)")

    if decision_quality is not None:
        lines.append(f"Decision Quality: {decision_quality}")
    else:
        lines.append("Decision Quality: N/A (no exits)")

    # False negatives
    if false_negatives:
        lines.append("")
        lines.append(f"FALSE NEGATIVES (30d): {len(false_negatives)}")
        for fn in false_negatives[:3]:
            lines.append(f"  {fn['ticker']}: rejected @ ${fn['rejection_price']:.2f}, peaked ${fn['peak_price']:.2f} (+{fn['move_pct']}%)")

    lines.append("")
    lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")

    return "\n".join(lines)


async def run() -> None:
    """Generate and send the weekly audit snapshot."""
    logger.info("Weekly audit snapshot starting")

    try:
        now = now_utc()
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()

        # Fetch week's data
        week_trades = db.get_trades_since(week_ago)
        week_scoring = db.get_scoring_runs_since(week_ago)
        week_alerts = db.get_alerts_since(week_ago)
        week_candidates = db.get_candidates_since(week_ago)

        # Compute quality metrics (use 30-day window for calibration)
        month_trades = db.get_trades_since(month_ago)
        month_scoring = db.get_scoring_runs_since(month_ago)

        calibration = _compute_calibration_score(month_trades, month_scoring)
        decision_quality = _compute_decision_quality(week_trades, week_scoring)
        false_negatives = _compute_false_negative_cost()

        # Format message
        text = _format_audit_message(
            week_trades, week_scoring, week_alerts, week_candidates,
            calibration, decision_quality, false_negatives,
        )

        # Send via Telegram
        sent = await send_telegram(text)

        # Log as alert
        db.insert_alert({
            "alert_type": "heartbeat",
            "priority": "normal",
            "title": "Weekly Audit Snapshot",
            "body": text[:500],
            "action_required": False,
            "channel": "telegram",
            "delivery_status": "sent" if sent else "failed",
            "delivery_attempts": 1,
            "sent_at": now.isoformat() if sent else None,
            "dedupe_key": f"weekly_audit_{now.strftime('%Y_%W')}",
            "created_at": now.isoformat(),
        })

        # Insert summary behavioral metric
        audit_ref_id = str(uuid.uuid4())
        if decision_quality is not None:
            db.insert_behavioral_metric({
                "metric_type": "plan_adherence",
                "reference_type": "scoring_run",
                "reference_id": audit_ref_id,
                "metric_value": decision_quality,
                "metric_unit": "percentage",
                "context": {
                    "type": "weekly_audit",
                    "week": now.strftime("%Y-W%W"),
                    "calibration": calibration,
                    "decision_quality": decision_quality,
                    "total_trades": len(week_trades),
                    "false_negatives": len(false_negatives),
                },
                "observed_at": now.isoformat(),
                "created_at": now.isoformat(),
            })

        logger.info("Weekly audit snapshot %s", "sent" if sent else "FAILED")

    except Exception as exc:
        logger.error("Weekly audit failed: %s", exc, exc_info=True)
        db.log_error_alert("weekly_audit", str(exc))


def main() -> None:
    """Entry point for GitHub Actions: python -m jobs.weekly_audit"""
    asyncio.run(run())


if __name__ == "__main__":
    main()
