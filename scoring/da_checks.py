"""
Devil's Advocate deterministic checks.

Each check returns: {"name": str, "verdict": "PROCEED"|"CAUTION"|"BLOCK", "detail": str}

Verdict aggregation:
- Any BLOCK => overall BLOCK
- Else any CAUTION => overall CAUTION
- Else PROCEED
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import config
import db

logger = logging.getLogger(__name__)


def _check_result(name: str, verdict: str, detail: str) -> dict[str, str]:
    return {"name": name, "verdict": verdict, "detail": detail}


# ── Individual checks ────────────────────────────────────────────────────────


def hard_ban_check(ticker: str) -> dict[str, str]:
    """Check if ticker is on the Hard Ban list."""
    bans = db.get_hard_bans()
    for rule in bans:
        logic = rule.get("rule_logic", {})
        # Check various ban types
        banned_tickers = logic.get("banned_tickers", [])
        if ticker.upper() in [t.upper() for t in banned_tickers]:
            return _check_result(
                "hard_ban_check",
                "BLOCK",
                f"Ticker {ticker} is hard-banned: {rule.get('rule_name', 'unnamed rule')}",
            )
        # Check asset type bans (would need position data)
        banned_types = logic.get("banned_types", [])
        if banned_types:
            # Position-level check done elsewhere; here we just check ticker-level bans
            pass
    return _check_result("hard_ban_check", "PROCEED", "No hard ban hit")


def concentration_cap_check(
    ticker: str,
    proposed_value: float,
    portfolio_nav: float,
) -> dict[str, str]:
    """Check if adding this position would exceed single-name concentration cap."""
    if portfolio_nav <= 0:
        return _check_result("concentration_cap_check", "CAUTION", "Portfolio NAV unknown or zero")

    # Get existing position value
    position = db.get_position_by_ticker(ticker)
    existing_value = float(position.get("market_value", 0) or 0) if position else 0.0
    projected_value = existing_value + proposed_value
    projected_pct = (projected_value / portfolio_nav) * 100

    if projected_pct > config.SINGLE_NAME_CAP_PCT * 1.5:
        return _check_result(
            "concentration_cap_check",
            "BLOCK",
            f"Projected {ticker} weight {projected_pct:.1f}% exceeds {config.SINGLE_NAME_CAP_PCT * 1.5:.0f}% hard cap",
        )
    if projected_pct > config.SINGLE_NAME_CAP_PCT:
        return _check_result(
            "concentration_cap_check",
            "CAUTION",
            f"Projected {ticker} weight {projected_pct:.1f}% exceeds {config.SINGLE_NAME_CAP_PCT:.0f}% cap",
        )
    return _check_result(
        "concentration_cap_check",
        "PROCEED",
        f"Projected weight {projected_pct:.1f}% within cap",
    )


def margin_utilization_check(
    proposed_value: float,
    current_margin_used: float,
    margin_limit: float,
) -> dict[str, str]:
    """Check if this trade would push margin utilization above cap."""
    if margin_limit <= 0:
        return _check_result("margin_utilization_check", "PROCEED", "Margin limit not configured")

    projected_util = ((current_margin_used + proposed_value) / margin_limit) * 100
    if projected_util > config.MARGIN_UTIL_CAP_PCT:
        return _check_result(
            "margin_utilization_check",
            "BLOCK",
            f"Projected margin utilization {projected_util:.1f}% exceeds {config.MARGIN_UTIL_CAP_PCT:.0f}% cap",
        )
    return _check_result(
        "margin_utilization_check",
        "PROCEED",
        f"Projected margin utilization {projected_util:.1f}% within cap",
    )


def cash_runway_check(cash_runway_months: float | None) -> dict[str, str]:
    """SC5 going concern flag based on cash runway."""
    if cash_runway_months is None:
        return _check_result("cash_runway_check", "CAUTION", "Cash runway data unavailable")
    if cash_runway_months < config.CASH_RUNWAY_BLOCK_MONTHS:
        return _check_result(
            "cash_runway_check",
            "BLOCK",
            f"Cash runway {cash_runway_months:.0f} months < {config.CASH_RUNWAY_BLOCK_MONTHS} month minimum",
        )
    if cash_runway_months < config.CASH_RUNWAY_CAUTION_MONTHS:
        return _check_result(
            "cash_runway_check",
            "CAUTION",
            f"Cash runway {cash_runway_months:.0f} months < {config.CASH_RUNWAY_CAUTION_MONTHS} month threshold",
        )
    return _check_result(
        "cash_runway_check",
        "PROCEED",
        f"Cash runway {cash_runway_months:.0f} months is adequate",
    )


def duplicate_catalyst_check(ticker: str, catalyst_date: date | None) -> dict[str, str]:
    """Check if already holding a position with same catalyst date."""
    if catalyst_date is None:
        return _check_result("duplicate_catalyst_check", "PROCEED", "No catalyst date to check")

    positions = db.get_active_positions()
    for pos in positions:
        if pos["ticker"].upper() == ticker.upper():
            continue  # skip self
        pos_cat_date = pos.get("catalyst_date")
        if pos_cat_date and str(pos_cat_date) == str(catalyst_date):
            return _check_result(
                "duplicate_catalyst_check",
                "CAUTION",
                f"Already holding {pos['ticker']} with same catalyst date {catalyst_date}",
            )
    return _check_result("duplicate_catalyst_check", "PROCEED", "No duplicate catalyst dates")


def max_positions_check() -> dict[str, str]:
    """Check if opening a new position would exceed position count limit."""
    positions = db.get_active_positions()
    count = len(positions)
    if count >= config.MAX_OPEN_POSITIONS:
        return _check_result(
            "max_positions_check",
            "BLOCK",
            f"Currently holding {count} positions, at max limit of {config.MAX_OPEN_POSITIONS}",
        )
    if count >= config.MAX_OPEN_POSITIONS - 2:
        return _check_result(
            "max_positions_check",
            "CAUTION",
            f"Currently holding {count}/{config.MAX_OPEN_POSITIONS} positions, approaching limit",
        )
    return _check_result(
        "max_positions_check",
        "PROCEED",
        f"Currently holding {count}/{config.MAX_OPEN_POSITIONS} positions",
    )


# ── Aggregate DA verdict ─────────────────────────────────────────────────────


def run_all_checks(
    ticker: str,
    catalyst_date: date | None = None,
    proposed_value: float = 0.0,
    portfolio_nav: float = 0.0,
    current_margin_used: float = 0.0,
    margin_limit: float = 0.0,
    cash_runway_months: float | None = None,
) -> dict[str, Any]:
    """
    Run all deterministic DA checks and return aggregated verdict.

    Returns:
        {
            "verdict": "PROCEED" | "CAUTION" | "BLOCK",
            "checks": [...],
            "highest_severity_check": str | None,
            "bear_summary": str,
        }
    """
    checks = [
        hard_ban_check(ticker),
        concentration_cap_check(ticker, proposed_value, portfolio_nav),
        margin_utilization_check(proposed_value, current_margin_used, margin_limit),
        cash_runway_check(cash_runway_months),
        duplicate_catalyst_check(ticker, catalyst_date),
        max_positions_check(),
    ]

    # Determine overall verdict
    has_block = any(c["verdict"] == "BLOCK" for c in checks)
    has_caution = any(c["verdict"] == "CAUTION" for c in checks)

    if has_block:
        overall = "BLOCK"
    elif has_caution:
        overall = "CAUTION"
    else:
        overall = "PROCEED"

    # Find highest severity check
    highest = None
    for c in checks:
        if c["verdict"] == "BLOCK":
            highest = c["name"]
            break
    if highest is None:
        for c in checks:
            if c["verdict"] == "CAUTION":
                highest = c["name"]
                break

    # Build bear summary from non-PROCEED checks
    bear_parts = [f"{c['name']}: {c['detail']}" for c in checks if c["verdict"] != "PROCEED"]
    bear_summary = "; ".join(bear_parts) if bear_parts else "All deterministic checks passed"

    return {
        "verdict": overall,
        "checks": checks,
        "highest_severity_check": highest,
        "bear_summary": bear_summary,
    }
