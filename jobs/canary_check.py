"""
Canary Health Check — Monitors system health and reports issues.

Runs every 6 hours via APScheduler. Only sends Telegram message
if there are WARNINGs or CRITICALs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

import db
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _check_supabase_health() -> tuple[str, str]:
    """Check Supabase connectivity."""
    try:
        if db.keepalive_ping():
            return "OK", "Supabase reachable"
        return "CRITICAL", "Supabase ping returned false"
    except Exception as exc:
        return "CRITICAL", f"Supabase unreachable: {exc}"


def _check_position_freshness() -> tuple[str, str]:
    """Check if position data is stale."""
    freshest = db.get_latest_position_freshness()
    if not freshest:
        return "WARNING", "No position sync recorded"

    try:
        if isinstance(freshest, str):
            fresh_dt = datetime.fromisoformat(freshest.replace("Z", "+00:00"))
        else:
            fresh_dt = freshest

        age = now_utc() - fresh_dt
        if age > timedelta(hours=24):
            hours = age.total_seconds() / 3600
            return "WARNING", f"Position data {hours:.0f}h old"
        return "OK", f"Position data {age.total_seconds() / 3600:.1f}h old"
    except Exception:
        return "WARNING", f"Cannot parse freshness: {freshest}"


def _check_missing_plans() -> tuple[str, str]:
    """Check positions with imminent catalysts but no plan."""
    missing = db.get_positions_missing_plans(within_days=7)
    if not missing:
        return "OK", "All imminent catalysts have plans"
    tickers = [p["ticker"] for p in missing[:5]]
    return "WARNING", f"Missing plans: {', '.join(tickers)}"


def _check_pending_reflections() -> tuple[str, str]:
    """Check for stale unreflected trades."""
    count = db.get_stale_reflection_count(hours=48)
    if count == 0:
        return "OK", "No stale reflections"
    return "WARNING", f"{count} trade(s) pending reflection >48h"


def _check_unacked_alerts() -> tuple[str, str]:
    """Check for unacknowledged alerts."""
    count = db.get_unacked_alerts_count(hours=24)
    if count == 0:
        return "OK", "No stale unacked alerts"
    return "WARNING", f"{count} alert(s) unacked >24h"


async def run() -> None:
    """Run all canary health checks."""
    logger.info("Canary health check starting")

    checks: list[tuple[str, str, str]] = []  # (name, level, detail)

    name_fn_pairs = [
        ("Supabase", _check_supabase_health),
        ("Position freshness", _check_position_freshness),
        ("Missing plans", _check_missing_plans),
        ("Pending reflections", _check_pending_reflections),
        ("Unacked alerts", _check_unacked_alerts),
    ]

    for name, fn in name_fn_pairs:
        try:
            level, detail = fn()
        except Exception as exc:
            level, detail = "WARNING", f"Check failed: {exc}"
        checks.append((name, level, detail))

    # Determine if we need to alert
    issues = [(n, l, d) for n, l, d in checks if l in ("WARNING", "CRITICAL")]
    criticals = [c for c in issues if c[1] == "CRITICAL"]

    if not issues:
        logger.info("Canary check: all OK")
        return

    # Format compact health report
    lines = ["CANARY HEALTH CHECK"]
    for name, level, detail in checks:
        icon = "🔴" if level == "CRITICAL" else "🟡" if level == "WARNING" else "🟢"
        lines.append(f"{icon} {name}: {detail}")

    lines.append("")
    lines.append(f"Issues: {len(criticals)} critical, {len(issues) - len(criticals)} warning")

    text = "\n".join(lines)
    await send_telegram(text)

    # Log as alert
    try:
        priority = "critical" if criticals else "high"
        db.insert_alert({
            "alert_type": "heartbeat",
            "priority": priority,
            "title": "Canary Health Check",
            "body": text[:500],
            "action_required": bool(criticals),
            "channel": "telegram",
            "delivery_status": "sent",
            "delivery_attempts": 1,
            "sent_at": now_utc().isoformat(),
            "dedupe_key": f"canary_{now_utc().strftime('%Y%m%d_%H')}",
            "created_at": now_utc().isoformat(),
        })
    except Exception as exc:
        logger.warning("Failed to log canary alert: %s", exc)

    # Insert behavioral metric for tracking
    try:
        db.insert_behavioral_metric({
            "metric_type": "alert_response_time",
            "reference_type": "alert",
            "reference_id": str(uuid.uuid4()),
            "metric_value": len(issues),
            "metric_unit": "count",
            "context": {
                "type": "canary_check",
                "checks": {n: {"level": l, "detail": d} for n, l, d in checks},
            },
            "observed_at": now_utc().isoformat(),
            "created_at": now_utc().isoformat(),
        })
    except Exception as exc:
        logger.warning("Failed to log canary metric: %s", exc)

    logger.info("Canary check: %d issues found", len(issues))


def main():
    """Entry point for GitHub Actions: python -m jobs.canary_check"""
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
