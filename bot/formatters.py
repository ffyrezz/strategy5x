"""
Message formatting helpers for Telegram.

Uses MarkdownV2 escaping for all output. Telegram MarkdownV2 requires
escaping these characters: _ * [ ] ( ) ~ ` > # + - = | { } . !
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from data.catalyst_calendar import days_until_catalyst, format_countdown
from utils.timezone import utc_to_sgt, now_sgt

# Characters that must be escaped in Telegram MarkdownV2
_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    result = []
    for char in str(text):
        if char in _ESCAPE_CHARS:
            result.append("\\")
        result.append(char)
    return "".join(result)


def _fmt_pnl(value: float | None) -> str:
    """Format P&L with sign."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}${value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    """Format percentage with sign."""
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


# ── Morning Brief ─────────────────────────────────────────────────────────────


def format_morning_brief(
    positions: list[dict[str, Any]],
    catalysts: list[dict[str, Any]],
    missing_plans: list[str],
    missing_scores: list[str],
    pending_acks: int,
) -> str:
    """
    Format the morning brief Telegram message.

    Returns plain text (not MarkdownV2) for readability.
    """
    today = now_sgt()
    date_str = today.strftime("%a %d %b %Y")

    # Portfolio summary
    total_value = sum(float(p.get("market_value") or 0) for p in positions)
    total_pnl = sum(float(p.get("unrealized_pnl") or 0) for p in positions)
    total_pnl_pct = (total_pnl / (total_value - total_pnl) * 100) if (total_value - total_pnl) > 0 else 0

    # Winners and losers
    sorted_pos = sorted(
        [p for p in positions if p.get("unrealized_pnl_pct") is not None],
        key=lambda p: float(p.get("unrealized_pnl_pct", 0)),
        reverse=True,
    )
    winners = [p for p in sorted_pos if float(p.get("unrealized_pnl_pct", 0)) > 0][:3]
    losers = [p for p in reversed(sorted_pos) if float(p.get("unrealized_pnl_pct", 0)) < 0][:3]

    # Build message
    lines = []
    lines.append(f"📊 MORNING BRIEF — {date_str}")
    lines.append("")
    lines.append(f"💰 Portfolio: ${total_value:,.0f} USD ({_fmt_pnl(total_pnl)} / {_fmt_pct(total_pnl_pct)})")

    if winners:
        w_str = ", ".join(f"{p['ticker']} {_fmt_pct(float(p.get('unrealized_pnl_pct', 0)))}" for p in winners)
        lines.append(f"📈 Winners: {w_str}")
    if losers:
        l_str = ", ".join(f"{p['ticker']} {_fmt_pct(float(p.get('unrealized_pnl_pct', 0)))}" for p in losers)
        lines.append(f"📉 Losers: {l_str}")

    # Catalysts
    lines.append("")
    if catalysts:
        lines.append("⚡ CATALYSTS THIS WEEK:")
        for cat in catalysts[:5]:
            days = days_until_catalyst(cat.get("catalyst_date"))
            countdown = format_countdown(days)
            cat_type = cat.get("catalyst_type", "event")
            warning = " ⚠️" if days is not None and days <= 3 else ""
            lines.append(f"• {cat['ticker']} {cat_type}: {cat.get('catalyst_date')} ({countdown}){warning}")
    else:
        lines.append("⚡ No catalysts this week.")

    # Action items
    actions = []
    for ticker in missing_plans[:3]:
        actions.append(f"Create pre-commitment plan for {ticker}")
    for ticker in missing_scores[:2]:
        actions.append(f"Score {ticker} (no recent scoring run)")
    if pending_acks > 0:
        actions.append(f"Acknowledge {pending_acks} pending alert(s)")

    if actions:
        lines.append("")
        lines.append("📋 ACTION ITEMS:")
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")

    # Timestamp
    lines.append("")
    lines.append(f"🔄 Updated: {today.strftime('%H:%M %Z')}")

    return "\n".join(lines)


# ── Portfolio ─────────────────────────────────────────────────────────────────


def format_portfolio(positions: list[dict[str, Any]]) -> str:
    """Format detailed portfolio listing."""
    if not positions:
        return "No live positions found in latest sync."

    total_value = sum(float(p.get("market_value") or 0) for p in positions)
    cash_positions = [p for p in positions if p.get("asset_type") == "cash"]
    equity_positions = [p for p in positions if p.get("asset_type") != "cash"]

    lines = []
    lines.append(f"Live portfolio: {len(equity_positions)} positions")
    lines.append(f"Total value: ${total_value:,.0f}")
    lines.append("")

    # Sort by market value descending
    sorted_pos = sorted(equity_positions, key=lambda p: float(p.get("market_value") or 0), reverse=True)

    for p in sorted_pos:
        mv = float(p.get("market_value") or 0)
        weight = (mv / total_value * 100) if total_value > 0 else 0
        pnl_pct = float(p.get("unrealized_pnl_pct") or 0)
        pnl_str = _fmt_pct(pnl_pct)
        line = f"  {p['ticker']}: ${mv:,.0f} ({weight:.1f}%) P&L: {pnl_str}"

        # Show extended hours price if available
        pre = p.get("pre_market_price")
        post = p.get("post_market_price")
        if pre:
            prev_close = float(p.get("previous_close") or p.get("avg_cost") or 0)
            if prev_close > 0:
                ext_chg = ((float(pre) - prev_close) / prev_close) * 100
                line += f" | 🌙 Pre: ${float(pre):.2f} ({ext_chg:+.1f}%)"
            else:
                line += f" | 🌙 Pre: ${float(pre):.2f}"
        elif post:
            prev_close = float(p.get("previous_close") or p.get("avg_cost") or 0)
            if prev_close > 0:
                ext_chg = ((float(post) - prev_close) / prev_close) * 100
                line += f" | 🌙 AH: ${float(post):.2f} ({ext_chg:+.1f}%)"
            else:
                line += f" | 🌙 AH: ${float(post):.2f}"

        lines.append(line)

    # Freshness
    if positions:
        freshest = max(
            (p.get("source_fresh_at") for p in positions if p.get("source_fresh_at")),
            default=None,
        )
        if freshest:
            lines.append("")
            lines.append(f"Last sync: {freshest}")

    return "\n".join(lines)


# ── Score Result ──────────────────────────────────────────────────────────────


def format_score_result(scoring_run: dict[str, Any]) -> str:
    """Format scoring run result for Telegram."""
    ticker = scoring_run.get("ticker", "???")
    version = scoring_run.get("scoring_version", "?")

    # SC axis line
    axes = []
    for i in range(1, 9):
        val = scoring_run.get(f"sc{i}")
        axes.append(str(int(val)) if val is not None else "-")
    sc_line = " / ".join(axes)

    composite = scoring_run.get("composite_score")
    verdict = scoring_run.get("verdict", "unknown")
    da_verdict = scoring_run.get("da_verdict", "PENDING")

    lines = [
        f"{ticker} scored | {version}",
        f"SC: {sc_line}",
    ]

    if composite is not None:
        # Determine bucket
        bucket = "D"
        from config import CONVICTION_BUCKETS
        for threshold, label in CONVICTION_BUCKETS:
            if composite >= threshold:
                bucket = label
                break
        lines.append(f"Total: {composite} | Bucket {bucket}")
    else:
        lines.append("Total: INCOMPLETE (missing axes)")

    # DA summary
    da_details = scoring_run.get("da_details", {})
    if isinstance(da_details, dict) and da_details.get("checks"):
        non_proceed = [c for c in da_details["checks"] if c.get("verdict") != "PROCEED"]
        if non_proceed:
            issues = "; ".join(f"{c['name']}: {c['detail']}" for c in non_proceed[:2])
            lines.append(f"DA: {da_verdict} — {issues}")
        else:
            lines.append(f"DA: {da_verdict}")
    else:
        lines.append(f"DA: {da_verdict}")

    # Missing data
    missing = [f"SC{i}" for i in range(1, 9) if scoring_run.get(f"sc{i}") is None]
    if missing:
        lines.append(f"Input gaps: {', '.join(missing)}")
    else:
        lines.append("Input gaps: none")

    return "\n".join(lines)


# ── Catalyst Alert (3 AM format) ─────────────────────────────────────────────


def format_catalyst_alert_3am(
    ticker: str,
    catalyst_type: str,
    countdown: str,
    plan: dict[str, Any] | None,
    position: dict[str, Any] | None,
    alert_id: str,
) -> str:
    """
    Format a catalyst alert for overnight delivery.
    MAX 5 LINES, plan first, single action.
    """
    lines = []

    # Line 1: Plan recall (most important)
    if plan:
        bear_action = "unknown"
        bull_action = "unknown"
        if isinstance(plan.get("if_rejection"), dict):
            bear_action = plan["if_rejection"].get("action", "unknown")
        elif isinstance(plan.get("if_rejection"), str):
            bear_action = plan["if_rejection"]
        if isinstance(plan.get("if_approval"), dict):
            bull_action = plan["if_approval"].get("action", "unknown")
        elif isinstance(plan.get("if_approval"), str):
            bull_action = plan["if_approval"]
        lines.append(f"PLAN: If CRL, {bear_action}. If approval, {bull_action}.")
    else:
        lines.append("⚠️ NO PLAN — create one now: /plan " + ticker)

    # Line 2: Event info
    lines.append(f"{ticker} {catalyst_type} {countdown}.")

    # Line 3: Position context
    if position:
        qty = position.get("quantity", "?")
        avg = position.get("avg_cost", "?")
        lines.append(f"Position: {qty} sh | avg {avg}.")
    else:
        lines.append("No open position.")

    # Line 4: Action
    lines.append(f"Reply: /ack {alert_id}")

    # Line 5: Deviation note
    lines.append("If execution deviates, record reason after market open.")

    return "\n".join(lines[:5])  # Enforce max 5 lines


# ── DA Verdict ────────────────────────────────────────────────────────────────


def format_da_verdict(da_result: dict[str, Any]) -> str:
    """Format DA verdict for Telegram."""
    verdict = da_result.get("verdict", "UNKNOWN")
    checks = da_result.get("checks", [])

    lines = [f"DA Verdict: {verdict}"]
    for check in checks:
        icon = "✅" if check["verdict"] == "PROCEED" else "⚠️" if check["verdict"] == "CAUTION" else "🛑"
        lines.append(f"  {icon} {check['name']}: {check['detail']}")

    return "\n".join(lines)


# ── Concentration ─────────────────────────────────────────────────────────────


def format_concentration(positions: list[dict[str, Any]], single_name_cap: float) -> str:
    """Format concentration breakdown."""
    if not positions:
        return "No positions to analyze."

    total_value = sum(float(p.get("market_value") or 0) for p in positions)
    if total_value <= 0:
        return "Portfolio value is zero — cannot compute concentration."

    sorted_pos = sorted(positions, key=lambda p: float(p.get("market_value") or 0), reverse=True)
    breaches = []
    near_cap = []

    lines = [f"Concentration check", f"Single-name cap: {single_name_cap:.1f}%"]
    lines.append("")

    for p in sorted_pos:
        mv = float(p.get("market_value") or 0)
        weight = (mv / total_value) * 100
        if weight > single_name_cap:
            breaches.append(f"{p['ticker']} {weight:.1f}%")
        elif weight > single_name_cap - 1.0:
            near_cap.append(f"{p['ticker']} {weight:.1f}%")

    if breaches:
        lines.append(f"Breaches: {', '.join(breaches)}")
    else:
        lines.append("Breaches: none")

    if near_cap:
        lines.append(f"Near cap (within 1%): {', '.join(near_cap)}")

    if breaches:
        lines.append("Suggested: reduce highest breach before adding new binary risk.")

    return "\n".join(lines)
