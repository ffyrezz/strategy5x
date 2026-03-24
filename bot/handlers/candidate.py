"""
/candidate TICKER — Show or create pipeline candidate details.

Usage:
  /candidate TICKER                          — view existing candidate
  /candidate TICKER catalyst=PDUFA date=2026-04-17 source=manual  — create new
"""

from __future__ import annotations

import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

import db
from data.market_data import get_price_data
from data.catalyst_calendar import days_until_catalyst, format_countdown
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def _parse_args(args: list[str]) -> tuple[str, dict[str, str]]:
    """Parse command args into (ticker, kwargs)."""
    if not args:
        return "", {}
    ticker = args[0].upper()
    kwargs = {}
    for arg in args[1:]:
        if "=" in arg:
            key, val = arg.split("=", 1)
            kwargs[key.lower()] = val
    return ticker, kwargs


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /candidate command."""
    args = context.args or []
    ticker, kwargs = _parse_args(args)

    if not ticker:
        await update.message.reply_text("Usage: /candidate TICKER [catalyst=TYPE date=YYYY-MM-DD source=SOURCE]")
        return

    # Check for hard bans first
    from scoring.da_checks import hard_ban_check
    ban_result = hard_ban_check(ticker)
    if ban_result["verdict"] == "BLOCK":
        await update.message.reply_text(f"🚫 {ticker} is hard-banned: {ban_result['detail']}")
        return

    # If no extra args, VIEW mode
    if not kwargs:
        candidate = db.get_candidate(ticker)
        if not candidate:
            await update.message.reply_text(
                f"Candidate not found for {ticker}.\n"
                f"Create: /candidate {ticker} catalyst=PDUFA date=2026-04-17 source=manual"
            )
            return

        # Format candidate info
        days = days_until_catalyst(candidate.get("catalyst_date"))
        countdown = format_countdown(days)
        status = candidate.get("status", "unknown")
        cat_type = candidate.get("catalyst_type", "unknown")
        cat_date = candidate.get("catalyst_date", "not set")

        lines = [
            f"{ticker} candidate status",
            f"Stage: {status}.",
            f"Catalyst: {cat_type} on {cat_date} ({countdown}).",
        ]

        # Latest score
        score_run = db.get_latest_scoring_run(ticker)
        if score_run:
            composite = score_run.get("composite_score", "?")
            da = score_run.get("da_verdict", "?")
            lines.append(f"Latest score: {composite} | DA: {da}.")
        else:
            lines.append("Latest score: none.")

        # Plan status
        plan = db.get_active_plan(ticker)
        lines.append(f"Plan: {'active' if plan else 'none'}.")

        # Next missing artifact
        missing = []
        if not score_run:
            missing.append("scoring run (/score)")
        if not plan and days is not None and days <= 14:
            missing.append("pre-commitment plan (/plan)")
        lines.append(f"Next missing: {', '.join(missing) if missing else 'none'}.")

        await update.message.reply_text("\n".join(lines))
        return

    # CREATE mode

    # ── Concentration awareness (v2.1) ──
    # Pipeline logging is always allowed — you need to track candidates early.
    # The concentration gate fires as a WARNING here, not a block.
    # The actual BLOCK lives in /trade (deployment stage).
    positions = db.get_active_positions()
    MAX_OPEN_POSITIONS = 5
    concentration_warning = ""
    if len(positions) >= MAX_OPEN_POSITIONS:
        position_tickers = [p["ticker"] for p in positions]
        concentration_warning = (
            f"\nNote: You have {len(positions)} open positions (max {MAX_OPEN_POSITIONS} for deployment).\n"
            f"Current: {', '.join(position_tickers)}\n"
            f"Pipeline logging OK. Deployment will be blocked until you exit a position."
        )

    # Fuzzy-match catalyst types to valid DB values
    CATALYST_MAP = {
        "PDUFA": "PDUFA", "ADCOM": "ADCOM",
        "PHASE3_READOUT": "PHASE3_READOUT", "PHASE3": "PHASE3_READOUT", "PH3": "PHASE3_READOUT",
        "PHASE2_READOUT": "PHASE2_READOUT", "PHASE2": "PHASE2_READOUT", "PH2": "PHASE2_READOUT",
        "PHASE2_DATA": "PHASE2_READOUT", "PHASE1_DATA": "OTHER",
        "REGEN": "REGEN", "EARNINGS": "EARNINGS", "MACRO": "MACRO", "OTHER": "OTHER",
    }
    SOURCE_MAP = {
        "manual": "manual", "biopharmcatalyst": "biopharmcatalyst", "news": "news", "tip": "tip",
    }
    raw_catalyst = kwargs.get("catalyst", "PDUFA").upper().replace(" ", "_")
    catalyst_type = CATALYST_MAP.get(raw_catalyst, "OTHER")
    catalyst_date_str = kwargs.get("date")
    raw_source = kwargs.get("source", "manual").lower()
    # Map any unknown source to the closest match
    source = SOURCE_MAP.get(raw_source)
    if not source:
        if "radar" in raw_source or "newsletter" in raw_source:
            source = "news"
        elif "lane" in raw_source:
            source = raw_source if raw_source.startswith("radar_lane_") else "manual"
        else:
            source = "manual"

    catalyst_date_val = None
    if catalyst_date_str:
        try:
            catalyst_date_val = date.fromisoformat(catalyst_date_str)
        except ValueError:
            await update.message.reply_text(f"Invalid date format: {catalyst_date_str}. Use YYYY-MM-DD.")
            return

    # Check for duplicates
    existing = db.get_candidate(ticker)
    if existing and str(existing.get("catalyst_date")) == str(catalyst_date_val):
        await update.message.reply_text(
            f"ℹ️ {ticker} already in pipeline (status: {existing.get('status')}). Use /score {ticker} to update."
        )
        return

    # Fetch initial price
    price_data = get_price_data(ticker)
    if price_data["price"] is None:
        await update.message.reply_text(f"❌ {ticker} not found — check symbol and retry.")
        return

    # Create candidate
    row = {
        "ticker": ticker,
        "company_name": price_data.get("name"),
        "status": "candidate",
        "status_history": [{"status": "candidate", "at": now_utc().isoformat(), "by": source}],
        "catalyst_type": catalyst_type,
        "catalyst_date": str(catalyst_date_val) if catalyst_date_val else None,
        "catalyst_confidence": "unverified",
        "discovery_source": source,
        "discovered_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }

    try:
        db.upsert_candidate(row)
        db.log_decision(
            event_type="radar_surfaced",
            ticker=ticker,
            source="user_manual",
            advice_summary=f"{ticker} added to pipeline. Catalyst: {catalyst_type} on {catalyst_date_str or 'TBD'}",
            advice_action="watch",
            price_at_event=price_data["price"],
            user_response="no_response_required",
        )
        days = days_until_catalyst(catalyst_date_val)
        countdown = format_countdown(days) if days is not None else ""
        await update.message.reply_text(
            f"✅ {ticker} added to pipeline.\n"
            f"Catalyst: {catalyst_type} on {catalyst_date_str or 'TBD'} {countdown}\n"
            f"Price at discovery: ${price_data['price']:.2f}\n"
            f"Next: /score {ticker}"
            f"{concentration_warning}"
        )
    except Exception as exc:
        logger.error("Failed to create candidate: %s", exc)
        await update.message.reply_text(f"Error creating candidate: {exc}")
