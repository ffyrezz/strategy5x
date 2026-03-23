"""
/score TICKER — Run deterministic scoring and DA checks.

Computes SC1 (catalyst timing), SC5 (cash runway), SC6 (liquidity),
SC7 (risk/reward) deterministically. SC2, SC3, SC4, SC8 are stubs.
"""

from __future__ import annotations

import logging
from datetime import date

from telegram import Update
from telegram.ext import ContextTypes

import config
import db
from data.market_data import get_price_data, get_cash_runway_months, get_analyst_targets
from bot.formatters import format_score_result
from scoring.engine import run_scoring
from scoring.da_checks import run_all_checks
from scoring.ai_dissent import get_ai_dissent, merge_with_deterministic

logger = logging.getLogger(__name__)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /score TICKER command."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /score TICKER")
        return

    ticker = args[0].upper()

    # Check candidate exists
    candidate = db.get_candidate(ticker)
    if not candidate:
        await update.message.reply_text(
            f"Cannot score: {ticker} is not in the pipeline.\nAdd it first: /candidate {ticker} catalyst=PDUFA date=YYYY-MM-DD"
        )
        return

    await update.message.reply_text(f"Scoring {ticker}... (fetching market data)")

    try:
        # Gather inputs
        price_data = get_price_data(ticker)
        cash_runway = get_cash_runway_months(ticker)
        targets = get_analyst_targets(ticker)

        # Parse catalyst date
        catalyst_date = None
        if candidate.get("catalyst_date"):
            try:
                catalyst_date = date.fromisoformat(str(candidate["catalyst_date"]))
            except ValueError:
                pass

        # Compute upside/downside for SC7
        upside_pct = None
        downside_pct = None
        current = price_data.get("price")
        if current and targets.get("target_mean") and targets.get("target_low"):
            upside_pct = ((targets["target_mean"] - current) / current) * 100
            downside_pct = ((current - targets["target_low"]) / current) * 100

        # Run scoring engine
        scoring_result = run_scoring(
            ticker=ticker,
            catalyst_date=catalyst_date,
            cash_runway_months=cash_runway,
            adv_30d_usd=price_data.get("adv_30d_usd"),
            upside_pct=upside_pct,
            downside_pct=downside_pct,
            current_price=current,
        )

        # Get rule version
        rule_version = db.get_current_rule_version()
        scoring_result["rule_version"] = rule_version
        scoring_result["playbook"] = candidate.get("playbook", "A")
        scoring_result["candidate_id"] = candidate.get("id")

        # Check for existing position
        position = db.get_position_by_ticker(ticker)
        if position:
            scoring_result["position_id"] = position.get("id")

        # Portfolio context
        positions = db.get_active_positions()
        total_nav = sum(float(p.get("market_value") or 0) for p in positions)
        scoring_result["portfolio_context"] = {
            "nav": total_nav,
            "position_count": len(positions),
        }

        # Run DA checks
        da_result = run_all_checks(
            ticker=ticker,
            catalyst_date=catalyst_date,
            portfolio_nav=total_nav,
            cash_runway_months=cash_runway,
        )

        scoring_result["da_verdict"] = da_result["verdict"]
        scoring_result["da_details"] = da_result
        scoring_result["bear_summary"] = da_result["bear_summary"]

        # Update verdict based on DA
        if da_result["verdict"] == "BLOCK":
            scoring_result["verdict"] = "block"
            scoring_result["verdict_reason"] = f"DA BLOCK: {da_result.get('highest_severity_check', 'unknown')}"

        # AI Dissent (feature-flagged)
        if config.AI_DISSENT_ENABLED and config.PERPLEXITY_API_KEY:
            try:
                ai_result = await get_ai_dissent(ticker, scoring_result)
                final_da, dissent_text = merge_with_deterministic(
                    scoring_result["da_verdict"], ai_result,
                )
                scoring_result["da_verdict"] = final_da
                if dissent_text:
                    scoring_result["da_dissent_text"] = dissent_text
                if ai_result.get("ai_enabled") and not ai_result.get("error"):
                    scoring_result["da_details"]["ai_dissent"] = {
                        "verdict": ai_result["verdict"],
                        "key_risks": ai_result["key_risks"],
                    }
            except Exception as exc:
                logger.warning("AI dissent failed for %s (continuing): %s", ticker, exc)

        # Remove internal field before DB insert
        axes_detail = scoring_result.pop("_axes_detail", None)

        # Save to database
        saved = db.insert_scoring_run(scoring_result)

        # Update candidate with latest score
        update_fields = {
            "latest_scoring_run_id": saved.get("id"),
            "latest_composite_score": scoring_result.get("composite_score"),
            "updated_at": scoring_result.get("created_at"),
        }
        # Update status if appropriate
        if scoring_result["verdict"] == "entry_ready" and candidate.get("status") in ("candidate", "watchlist"):
            update_fields["status"] = "scoring"
        db.update_candidate(candidate["id"], update_fields)

        # Format and send
        text = format_score_result(scoring_result)
        await update.message.reply_text(text)

    except Exception as exc:
        logger.error("Scoring failed for %s: %s", ticker, exc, exc_info=True)
        await update.message.reply_text(f"⚠️ Scoring failed for {ticker}: {exc}")
