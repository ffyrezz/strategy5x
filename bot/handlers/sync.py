"""
CSV Sync — Accept Moomoo CSV documents via Telegram.

Handles two CSV types:
  1. Positions-Margin-Account — upserts position snapshots
  2. Orders-Margin-Account — logs filled trades, closes ghost positions

The bot auto-detects the CSV type from the header row.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

import db
from utils.provenance import CSV
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

BROKER_ACCOUNT_ID = "8352"


def _parse_csv_content(content: str) -> list[dict[str, Any]]:
    """Parse Moomoo CSV content into position rows."""
    positions = []
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        try:
            # Flexible column name matching for Moomoo CSV format
            def _get(row, *names, default="0"):
                for n in names:
                    v = row.get(n)
                    if v is not None and str(v).strip() not in ("", "--"):
                        return str(v).strip()
                return default

            ticker = _get(row, "Symbol", "symbol", default="").upper()
            if not ticker:
                continue

            qty = float(_get(row, "Quantity", "Qty", "qty").replace(",", ""))
            # Allow qty=0 rows if they have realized P&L (closed positions like KPTI)
            # but skip truly empty rows
            if qty <= 0:
                # Check if this row has realized P&L worth capturing
                has_realized = _get(row, "Realized P/L", "Realized P&L", default="0").replace(",", "").replace("$", "").replace("+", "").replace("-", "")
                if not has_realized or float(has_realized) == 0:
                    continue
                # This is a closed position with realized P&L — still include for tracking

            avg_cost = float(_get(row, "Average Cost", "Avg Cost", "avg_cost").replace(",", "").replace("$", ""))
            last_price = float(_get(row, "Current price", "Last Price", "last_price", "Last").replace(",", "").replace("$", "")) or None
            market_value = float(_get(row, "Market Value", "market_value").replace(",", "").replace("$", "")) or None
            pnl = float(_get(row, "Unrealized P/L", "Unrealized P&L", "unrealized_pnl").replace(",", "").replace("$", "").replace("+", "")) or None
            pnl_pct_str = _get(row, "% Unrealized P/L", "Unrealized P&L %", "unrealized_pnl_pct").replace(",", "").replace("%", "").replace("+", "")
            pnl_pct = float(pnl_pct_str) if pnl_pct_str else None

            # New P&L fields from Moomoo
            realized_pnl_str = _get(row, "Realized P/L", "Realized P&L", default="0").replace(",", "").replace("$", "").replace("+", "")
            realized_pnl = float(realized_pnl_str) if realized_pnl_str else 0
            total_pnl_str = _get(row, "Total P/L", "Total P&L", default="0").replace(",", "").replace("$", "").replace("+", "")
            total_pnl = float(total_pnl_str) if total_pnl_str else None
            today_pnl_str = _get(row, "Today's P/L", "Today P&L", default="0").replace(",", "").replace("$", "").replace("+", "")
            today_pnl = float(today_pnl_str) if today_pnl_str else 0

            name = (row.get("Name") or row.get("name") or "").strip() or None

            hash_input = json.dumps({"ticker": ticker, "qty": qty, "avg_cost": avg_cost, "last_price": last_price})
            pos_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

            now = now_utc()
            positions.append({
                "broker_account_id": BROKER_ACCOUNT_ID,
                "ticker": ticker,
                "security_name": name,
                "asset_type": "equity",
                "quantity": qty,
                "avg_cost": avg_cost,
                "last_price": last_price,
                "market_value": market_value,
                "unrealized_pnl": pnl,
                "unrealized_pnl_pct": pnl_pct,
                "realized_pnl": realized_pnl,
                "total_pnl": total_pnl,
                "today_pnl": today_pnl,
                "currency": "USD",
                "status": "open",
                "source_ref": CSV("moomoo_telegram_sync"),
                "source_fresh_at": now.isoformat(),
                "position_hash": pos_hash,
            })
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping CSV row: %s — %s", row, exc)

    return positions


def _detect_csv_type(content: str, file_name: str = "") -> str:
    """Detect whether CSV is a Positions, Orders, or History export from Moomoo.

    History CSVs look like Orders but contain ALL historical trades (filled,
    queued, cancelled).  Importing them as orders would re-create every past
    trade.  We detect History CSVs via:
      1. Filename contains 'History'
      2. Header row contains fee columns ('Platform Fees', 'Settlement Fees')
    """
    first_line = content.split("\n", 1)[0].lower()

    # --- History CSV guard ---
    if "history" in file_name.lower():
        return "history"
    # History CSVs have fee breakdown columns that Orders CSVs lack
    if "platform fees" in first_line or "settlement fees" in first_line:
        return "history"

    if "filled@avg price" in first_line or "order price" in first_line or "fill qty" in first_line:
        return "orders"
    if "average cost" in first_line or "unrealized" in first_line or "market value" in first_line:
        return "positions"
    # Fallback: check for "Side" column (Orders have it, Positions don't)
    if "side" in first_line and "fill price" in first_line:
        return "orders"
    return "positions"


def _parse_orders_csv(content: str) -> list[dict[str, Any]]:
    """Parse Moomoo Orders CSV into trade rows."""
    trades = []
    reader = csv.DictReader(io.StringIO(content))

    for row in reader:
        try:
            def _get(row, *names, default=""):
                for n in names:
                    v = row.get(n)
                    if v is not None and str(v).strip() not in ("", "--"):
                        return str(v).strip()
                return default

            status = _get(row, "Status", "status").lower()
            if status != "filled":
                continue  # Only process filled orders

            ticker = _get(row, "Symbol", "symbol").upper()
            if not ticker:
                continue

            side = _get(row, "Side", "side").upper()
            if side not in ("BUY", "SELL"):
                continue

            # Parse fill quantity and price (more reliable than order qty/price)
            fill_qty_str = _get(row, "Fill Qty", "fill_qty", default="0").replace(",", "")
            fill_qty = float(fill_qty_str)
            if fill_qty <= 0:
                # Fallback to order qty
                fill_qty = float(_get(row, "Order Qty", "order_qty", default="0").replace(",", ""))
            if fill_qty <= 0:
                continue

            fill_price_str = _get(row, "Fill Price", "fill_price", default="0").replace(",", "").replace("$", "")
            fill_price = float(fill_price_str)
            if fill_price <= 0:
                # Try parsing from "Filled@Avg Price" field (format: "188@5.5108")
                filled_avg = _get(row, "Filled@Avg Price", "filled_avg_price")
                if "@" in filled_avg:
                    parts = filled_avg.split("@")
                    fill_price = float(parts[1])
                    if fill_qty <= 0:
                        fill_qty = float(parts[0])
            if fill_price <= 0:
                continue

            fill_amount_str = _get(row, "Fill Amount", "fill_amount", default="0").replace(",", "").replace("$", "")
            fill_value = float(fill_amount_str) if fill_amount_str else round(fill_qty * fill_price, 2)

            name = _get(row, "Name", "name") or None
            order_time = _get(row, "Order Time", "order_time") or None
            fill_time = _get(row, "Fill Time", "fill_time") or None
            order_type = _get(row, "Order Type", "order_type") or None

            now = now_utc()
            trades.append({
                "ticker": ticker,
                "side": side,
                "quantity": fill_qty,
                "fill_price": fill_price,
                "fill_value": fill_value,
                "security_name": name,
                "order_time": order_time,
                "fill_time": fill_time,
                "order_type": order_type,
                # Fields for db.insert_trade()
                "broker_account_id": BROKER_ACCOUNT_ID,
                "filled_at": now.isoformat(),
                "trade_context": "catalyst_exit" if side == "SELL" else "catalyst_entry",
                "is_entry": side == "BUY",
                "source_ref": CSV("moomoo_orders_sync"),
                "user_confirmed": True,
                "reflection_completed": False,
                "created_at": now.isoformat(),
            })
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping Orders CSV row: %s — %s", row, exc)

    return trades


async def _process_orders(update: Update, content: str, file_name: str) -> None:
    """Process an Orders CSV: log trades, close sold-out positions, log to decision trail."""
    trades = _parse_orders_csv(content)
    if not trades:
        await update.message.reply_text(f"No filled orders found in {file_name}.")
        return

    lines = [f"Orders sync: {len(trades)} filled order(s) from {file_name}"]
    logged_count = 0
    closed_positions = []

    for t in trades:
        ticker = t["ticker"]
        side = t["side"]
        qty = t["quantity"]
        price = t["fill_price"]

        # Duplicate guard: skip if we already have this exact trade
        existing = db.get_client().table("trades").select("id").eq(
            "ticker", ticker
        ).eq("side", side).eq("quantity", qty).eq(
            "fill_price", price
        ).eq("source_ref", CSV("moomoo_orders_sync")).execute()
        if existing.data:
            lines.append(f"  Skip (dup) {side} {qty:.0f} {ticker} @ ${price:.4f}")
            continue

        # Check for existing position
        position = db.get_position_by_ticker(ticker)

        # Look up related records for the trade row
        scoring_run = db.get_latest_scoring_run(ticker)
        plan = db.get_active_plan(ticker)

        trade_row = {
            "broker_account_id": t["broker_account_id"],
            "ticker": ticker,
            "side": side,
            "quantity": qty,
            "fill_price": price,
            "fill_value": t["fill_value"],
            "filled_at": t["filled_at"],
            "position_id": position.get("id") if position else None,
            "scoring_run_id": scoring_run.get("id") if scoring_run else None,
            "precommitment_plan_id": plan.get("id") if plan else None,
            "trade_context": t["trade_context"],
            "plan_adherence": "followed" if plan and side == "SELL" else ("no_plan" if side == "SELL" else None),
            "is_entry": t["is_entry"],
            "source_ref": t["source_ref"],
            "user_confirmed": True,
            "reflection_completed": False,
            "created_at": t["created_at"],
        }

        try:
            saved = db.insert_trade(trade_row)
            trade_id = saved.get("id") if saved else None
            logged_count += 1

            fill_time = t.get("fill_time") or ""
            lines.append(f"  {side} {qty:.0f} {ticker} @ ${price:.4f} ({fill_time})")

            # If SELL and position exists, check if fully closed
            if side == "SELL" and position:
                pos_qty = float(position.get("quantity", 0))
                if qty >= pos_qty:
                    # Full exit — mark position as closed
                    try:
                        db.get_client().table("positions").update({
                            "status": "closed",
                            "updated_at": now_utc().isoformat(),
                        }).eq("id", position["id"]).execute()
                        closed_positions.append(ticker)
                        lines.append(f"    Position closed: {ticker} (was {pos_qty:.0f} shares)")
                    except Exception as exc:
                        logger.warning("Failed to close position %s: %s", ticker, exc)

            # Log to decision audit trail
            db.log_decision(
                event_type="user_action",
                ticker=ticker,
                source="trade_handler",
                advice_summary=f"Order synced: {side} {qty:.0f} {ticker} @ ${price:.4f}",
                advice_action="buy" if side == "BUY" else "sell",
                trade_id=trade_id,
                position_id=position.get("id") if position else None,
                price_at_event=price,
                user_response="followed" if plan else "no_response_required",
            )

        except Exception as exc:
            logger.warning("Failed to log trade for %s: %s", ticker, exc)
            lines.append(f"  Failed to log {side} {ticker}: {exc}")

    if closed_positions:
        lines.append(f"Positions closed: {', '.join(closed_positions)}")
        lines.append("Ghost positions resolved.")

    lines.append(f"Logged: {logged_count}/{len(trades)} trades")
    lines.append(f"Synced at: {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")

    await update.message.reply_text("\n".join(lines))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a CSV file sent as a document attachment."""
    document = update.message.document
    if not document:
        return

    # Only process CSV files
    file_name = document.file_name or ""
    if not file_name.lower().endswith(".csv"):
        return

    await update.message.reply_text(f"Processing CSV: {file_name}...")

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        # Handle BOM encoding from Moomoo CSV exports
        content = file_bytes.decode("utf-8-sig")

        # Auto-detect CSV type and route accordingly
        csv_type = _detect_csv_type(content, file_name)

        if csv_type == "history":
            await update.message.reply_text(
                f"Rejected: {file_name}\n\n"
                "This is a History CSV (all past orders). "
                "Importing it would re-create every historical trade.\n\n"
                "Send an Orders CSV (recent fills only) or a Positions CSV instead."
            )
            return

        if csv_type == "orders":
            await _process_orders(update, content, file_name)
            return

        # --- Positions CSV processing (original logic) ---
        positions = _parse_csv_content(content)
        if not positions:
            await update.message.reply_text("No valid positions found in CSV.")
            return

        csv_tickers = {p["ticker"] for p in positions}

        # Get existing open tickers
        existing_tickers = set(db.get_all_open_tickers())

        # Upsert all positions
        db.upsert_positions(positions)

        # Detect new tickers (in CSV but not in DB)
        new_tickers = csv_tickers - existing_tickers
        # Detect ghost positions (in DB but not in CSV)
        ghost_tickers = existing_tickers - csv_tickers

        # Build summary
        lines = [
            f"Sync complete: {len(positions)} positions from {file_name}",
            f"Total tickers: {len(csv_tickers)}",
        ]

        if new_tickers:
            lines.append(f"New tickers: {', '.join(sorted(new_tickers))}")

        if ghost_tickers:
            lines.append(f"Ghost positions (in DB, not in CSV): {', '.join(sorted(ghost_tickers))}")

        total_value = sum(float(p.get("market_value") or 0) for p in positions)
        lines.append(f"Total market value: ${total_value:,.0f}")
        lines.append(f"Synced at: {now_utc().strftime('%Y-%m-%d %H:%M UTC')}")

        await update.message.reply_text("\n".join(lines))

    except Exception as exc:
        logger.error("CSV sync failed: %s", exc, exc_info=True)
        await update.message.reply_text(f"CSV sync failed: {exc}")
