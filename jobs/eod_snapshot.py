"""
Scheduled job: End-of-Day Portfolio Snapshot.

Runs after US market close (~21:30 UTC = 5:30 AM SGT, weekdays).
Captures every open position's closing price from Finnhub and writes
one row per position + one _TOTAL summary row to portfolio_snapshots.

This data powers the self-calculating P/L Calendar — the system no
longer needs manually-fed Moomoo numbers to show daily P/L.
"""

from __future__ import annotations

import logging
from datetime import date

import config
import db
from data.finnhub_data import get_finnhub_quote
from utils.timezone import now_utc, today_et

logger = logging.getLogger(__name__)

# Hardcoded cash until Moomoo API integration (Phase 2).
# Updated whenever a Positions CSV is synced.
CASH_USD = 24.96


def _get_us_trading_date() -> date:
    """Return today's US trading date (ET)."""
    return today_et()


def run() -> None:
    """Take an end-of-day portfolio snapshot."""
    snap_date = _get_us_trading_date()
    logger.info("EOD snapshot starting for %s", snap_date)

    # Check if we already have a snapshot for today
    existing = (
        db.get_client()
        .table("portfolio_snapshots")
        .select("id")
        .eq("snap_date", snap_date.isoformat())
        .eq("ticker", "_TOTAL")
        .execute()
    )
    if existing.data:
        logger.info("Snapshot already exists for %s, skipping", snap_date)
        return

    # Get all open positions
    positions = (
        db.get_client()
        .table("positions")
        .select("*")
        .eq("status", "open")
        .execute()
        .data or []
    )

    if not positions:
        logger.warning("No open positions found, skipping snapshot")
        return

    rows = []
    total_mv = 0.0
    total_cost = 0.0
    total_unrealized = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        qty = float(pos.get("quantity") or 0)
        avg_cost = float(pos.get("avg_cost") or 0)

        if qty <= 0:
            continue

        # Fetch closing price from Finnhub
        quote = get_finnhub_quote(ticker)
        close_price = quote.get("price") or float(pos.get("last_price") or 0)

        mv = round(qty * close_price, 2)
        cost_basis = round(qty * avg_cost, 2)
        unrealized = round(mv - cost_basis, 2)

        total_mv += mv
        total_cost += cost_basis
        total_unrealized += unrealized

        rows.append({
            "snap_date": snap_date.isoformat(),
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": avg_cost,
            "close_price": close_price,
            "market_value": mv,
            "unrealized_pnl": unrealized,
            "cost_basis": cost_basis,
            "cash": 0,
            "total_portfolio_value": 0,  # only meaningful on _TOTAL
            "source": "eod_finnhub",
        })

        logger.info(
            "  %s: %s sh @ $%.2f = $%.2f (cost $%.2f, unr $%.2f)",
            ticker, qty, close_price, mv, cost_basis, unrealized,
        )

    # Summary row
    total_portfolio = round(total_mv + CASH_USD, 2)
    rows.append({
        "snap_date": snap_date.isoformat(),
        "ticker": "_TOTAL",
        "quantity": 0,
        "avg_cost": 0,
        "close_price": 0,
        "market_value": round(total_mv, 2),
        "unrealized_pnl": round(total_unrealized, 2),
        "cost_basis": round(total_cost, 2),
        "cash": CASH_USD,
        "total_portfolio_value": total_portfolio,
        "source": "eod_finnhub",
    })

    # Upsert all rows (unique on snap_date + ticker)
    client = db.get_client()
    for row in rows:
        try:
            client.table("portfolio_snapshots").upsert(
                row, on_conflict="snap_date,ticker"
            ).execute()
        except Exception as exc:
            logger.error("Failed to upsert snapshot row %s/%s: %s", row["snap_date"], row["ticker"], exc)

    logger.info(
        "EOD snapshot complete for %s: %d positions, MV=$%.2f, cash=$%.2f, total=$%.2f",
        snap_date, len(positions), total_mv, CASH_USD, total_portfolio,
    )
