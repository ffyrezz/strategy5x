"""
/trade TICKER SIDE QTY PRICE — Log a trade entry or exit.

Usage:
  /trade RCKT BUY 188 4.23
  /trade RCKT SELL 100 5.50
  /trade RCKT SELL 100 5.50 context=take_profit
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

VALID_SIDES = {"BUY", "SELL"}
VALID_CONTEXTS = {
    "catalyst_entry", "catalyst_exit", "scoring_entry",
    "stop_loss", "take_profit", "rebalance", "manual",
    "dca", "trim", "close_all", "other",
}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /trade TICKER SIDE QTY PRICE [context=...]."""
    args = context.args or []
    if len(args) < 4:
        await update.message.reply_text(
            "Usage: /trade TICKER BUY|SELL QUANTITY PRICE [context=catalyst_entry]\n"
            "Example: /trade RCKT BUY 188 4.23"
        )
        return

    ticker = args[0].upper()
    side = args[1].upper()
    if side not in VALID_SIDES:
        await update.message.reply_text(f"Invalid side: {side}. Must be BUY or SELL.")
        return

    try:
        quantity = float(args[2])
        fill_price = float(args[3])
    except ValueError:
        await update.message.reply_text("Quantity and price must be numbers.")
        return

    if quantity <= 0 or fill_price <= 0:
        await update.message.reply_text("Quantity and price must be positive.")
        return

    # Parse optional context= arg
    trade_context = "catalyst_entry" if side == "BUY" else "catalyst_exit"
    for arg in args[4:]:
        if arg.startswith("context="):
            ctx_val = arg.split("=", 1)[1].lower()
            if ctx_val in VALID_CONTEXTS:
                trade_context = ctx_val
            else:
                await update.message.reply_text(
                    f"Invalid context: {ctx_val}\n"
                    f"Allowed: {', '.join(sorted(VALID_CONTEXTS))}"
                )
                return

    fill_value = round(quantity * fill_price, 2)

    # ── Concentration gate (v2.1) — blocks new BUY if at capacity ──
    MAX_OPEN_POSITIONS = 5
    if side == "BUY":
        positions = db.get_active_positions()
        existing_position = any(p["ticker"] == ticker for p in positions)
        # Only block if this is a NEW position (not adding to existing)
        if not existing_position and len(positions) >= MAX_OPEN_POSITIONS:
            position_tickers = [p["ticker"] for p in positions]
            # Check for override
            has_override = any(a.startswith("override=") and a.split("=", 1)[1].lower() == "true" for a in args[4:])
            if not has_override:
                await update.message.reply_text(
                    f"CONCENTRATION BLOCK: You have {len(positions)} open positions (max {MAX_OPEN_POSITIONS}).\n"
                    f"Current: {', '.join(position_tickers)}\n\n"
                    f"{ticker} is not an existing position — this would be position #{len(positions)+1}.\n"
                    f"Exit a position first, then retry.\n"
                    f"To override: add override=true to the command"
                )
                return

    # Look up related records
    position = db.get_position_by_ticker(ticker)
    scoring_run = db.get_latest_scoring_run(ticker)
    plan = db.get_active_plan(ticker)

    # Determine plan adherence for SELL trades
    plan_adherence = None
    if side == "SELL":
        plan_adherence = "followed" if plan else "no_plan"

    now = now_utc()

    trade_row = {
        "broker_account_id": "8352",
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "fill_price": fill_price,
        "fill_value": fill_value,
        "filled_at": now.isoformat(),
        "position_id": position.get("id") if position else None,
        "scoring_run_id": scoring_run.get("id") if scoring_run else None,
        "precommitment_plan_id": plan.get("id") if plan else None,
        "trade_context": trade_context,
        "plan_adherence": plan_adherence,
        "is_entry": side == "BUY",
        "source_ref": "[MANUAL] user via Telegram",
        "user_confirmed": True,
        "reflection_completed": False,
        "created_at": now.isoformat(),
    }

    try:
        saved = db.insert_trade(trade_row)

        lines = [
            f"Trade logged: {side} {quantity:.0f} {ticker} @ ${fill_price:.2f}",
            f"Value: ${fill_value:,.2f} | Context: {trade_context}",
        ]

        if position:
            lines.append(f"Position: {position.get('quantity', '?')} sh @ ${position.get('avg_cost', '?')}")

        if plan and side == "SELL":
            lines.append(f"Plan adherence: {plan_adherence}")
            lines.append("Complete reflection: /reflect " + ticker)

        if scoring_run:
            composite = scoring_run.get("composite_score")
            verdict = scoring_run.get("verdict")
            lines.append(f"Latest score: {composite} ({verdict})")

        if side == "SELL" and not plan:
            lines.append("No pre-commitment plan was active for this exit.")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("Failed to log trade for %s: %s", ticker, exc, exc_info=True)
        await update.message.reply_text(f"Error logging trade: {exc}")
