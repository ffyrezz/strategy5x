"""
/plan TICKER — Show or create pre-commitment plan.

Usage:
  /plan TICKER                              — view active plan
  /plan TICKER bull="..." bear="..." mixed="..."  — create new plan
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

import db
from data.catalyst_calendar import days_until_catalyst, format_countdown
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _parse_plan_args(args: list[str]) -> tuple[str, dict[str, str]]:
    """Parse plan command args. Handles quoted values with spaces."""
    if not args:
        return "", {}

    ticker = args[0].upper()
    raw = " ".join(args[1:])

    # Extract key="value" pairs
    kwargs = {}
    pattern = r'(\w+)="([^"]*)"'
    for match in re.finditer(pattern, raw):
        kwargs[match.group(1).lower()] = match.group(2)

    # Also try key=value (unquoted)
    if not kwargs:
        for arg in args[1:]:
            if "=" in arg:
                key, val = arg.split("=", 1)
                kwargs[key.lower()] = val.strip('"')

    return ticker, kwargs


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /plan command."""
    args = context.args or []
    ticker, kwargs = _parse_plan_args(args)

    if not ticker:
        await update.message.reply_text(
            'Usage:\n'
            '  /plan TICKER — view active plan\n'
            '  /plan TICKER bull="action" bear="action" mixed="action"'
        )
        return

    # Check candidate exists
    candidate = db.get_candidate(ticker)
    if not candidate:
        await update.message.reply_text(f"No active candidate found for {ticker}.")
        return

    cat_date = candidate.get("catalyst_date")
    VALID_CATALYST_TYPES = {"PDUFA", "ADCOM", "PHASE3_READOUT", "PHASE2_READOUT", "REGEN", "EARNINGS", "MACRO", "OTHER"}
    raw_type = candidate.get("catalyst_type", "OTHER").upper()
    cat_type = raw_type if raw_type in VALID_CATALYST_TYPES else "OTHER"

    if not cat_date:
        # Allow plan creation with a placeholder date for "any day" catalysts
        # Use end of current month as outer bound
        from datetime import date
        today = date.today()
        if today.month == 12:
            cat_date = date(today.year + 1, 1, 31)
        else:
            import calendar
            last_day = calendar.monthrange(today.year, today.month)[1]
            cat_date = date(today.year, today.month, last_day)
        await update.message.reply_text(
            f"⚠️ {ticker} has no confirmed catalyst date. Using {cat_date} as outer bound.\n"
            f"Update with: /candidate {ticker} catalyst=TYPE date=YYYY-MM-DD"
        )

    # VIEW mode — no plan args provided
    if not kwargs:
        plan = db.get_active_plan(ticker)
        if not plan:
            days = days_until_catalyst(cat_date)
            countdown = format_countdown(days)
            await update.message.reply_text(
                f"{ticker} | {cat_type} | {cat_date} ({countdown})\n"
                f"No active plan.\n"
                f'Create: /plan {ticker} bull="action" bear="action" mixed="action"'
            )
            return

        # Display existing plan
        lines = [
            f"{ticker} | {cat_type} | {cat_date}",
            f"Plan: active (created {plan.get('created_at', '?')[:10]}).",
        ]

        # Extract plan text from JSON or string fields
        for scenario, label in [("if_approval", "Bull"), ("if_rejection", "Bear"), ("if_mixed", "Mixed")]:
            val = plan.get(scenario)
            if isinstance(val, dict):
                text = val.get("action", val.get("notes", str(val)))
            elif isinstance(val, str):
                text = val
            else:
                text = "not set"
            lines.append(f"{label}: {text}")

        # DA warning if any
        score_run = db.get_latest_scoring_run(ticker)
        if score_run and score_run.get("da_verdict") in ("CAUTION", "BLOCK"):
            lines.append(f"DA: {score_run['da_verdict']} — {score_run.get('bear_summary', '')[:100]}")

        await update.message.reply_text("\n".join(lines))
        return

    # CREATE mode — plan args provided
    bull = kwargs.get("bull")
    bear = kwargs.get("bear")
    mixed = kwargs.get("mixed")

    if not bull or not bear or not mixed:
        await update.message.reply_text(
            f"Plan rejected: bull, bear, and mixed branches are all required.\n"
            f'Usage: /plan {ticker} bull="action" bear="action" mixed="action"'
        )
        return

    # Get position context — position_id is NOT NULL in schema
    position = db.get_position_by_ticker(ticker)
    if not position:
        await update.message.reply_text(
            f"Cannot create plan: no open position for {ticker}.\n"
            "Plans require a position. Open a position first, then create a plan."
        )
        return

    # Deactivate old plans for this ticker
    old_plan = db.get_active_plan(ticker)
    if old_plan:
        try:
            db.get_client().table("precommitment_plans").update(
                {"is_active": False}
            ).eq("id", old_plan["id"]).execute()
        except Exception as exc:
            logger.warning("Failed to deactivate old plan: %s", exc)

    # Create new plan
    plan_row = {
        "ticker": ticker,
        "position_id": position["id"],
        "candidate_id": candidate.get("id"),
        "catalyst_date": str(cat_date),
        "catalyst_type": cat_type,
        "if_approval": {"action": bull, "size_pct": None},
        "if_rejection": {"action": bear, "size_pct": None},
        "if_mixed": {"action": mixed, "size_pct": None},
        "position_size_at_plan": float(position.get("market_value", 0)),
        "entry_price_at_plan": float(position.get("avg_cost", 0)),
        "is_active": True,
        "created_at": now_utc().isoformat(),
    }

    try:
        saved_plan = db.insert_plan(plan_row)

        db.log_decision(
            event_type="plan_created",
            ticker=ticker,
            source="plan",
            advice_summary=f"{ticker} plan: bull={bull}, bear={bear}, mixed={mixed}",
            advice_action="no_action",
            plan_id=saved_plan.get("id"),
            position_id=position.get("id"),
            price_at_event=float(position.get("last_price") or position.get("avg_cost") or 0) or None,
            user_response="no_response_required",
        )

        days = days_until_catalyst(cat_date)
        countdown = format_countdown(days)

        lines = [
            f"{ticker} | {cat_type} | {cat_date} ({countdown})",
            "Plan saved: active.",
            f"Bull: {bull}",
            f"Bear: {bear}",
            f"Mixed: {mixed}",
        ]

        # DA warning
        score_run = db.get_latest_scoring_run(ticker)
        if score_run and score_run.get("da_verdict") in ("CAUTION", "BLOCK"):
            lines.append(f"DA: {score_run['da_verdict']} — {score_run.get('bear_summary', '')[:100]}")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("Failed to save plan: %s", exc)
        await update.message.reply_text(f"Error saving plan: {exc}")
