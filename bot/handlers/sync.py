"""
CSV Position Sync — Accept a Moomoo CSV document via Telegram and update positions.

The user sends a CSV file (Positions-Margin-Account-8352 format) as a document
attachment. The bot parses it and upserts positions into Supabase.
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
            if qty <= 0:
                continue

            avg_cost = float(_get(row, "Average Cost", "Avg Cost", "avg_cost").replace(",", "").replace("$", ""))
            last_price = float(_get(row, "Current price", "Last Price", "last_price", "Last").replace(",", "").replace("$", "")) or None
            market_value = float(_get(row, "Market Value", "market_value").replace(",", "").replace("$", "")) or None
            pnl = float(_get(row, "Unrealized P/L", "Unrealized P&L", "unrealized_pnl").replace(",", "").replace("$", "")) or None
            pnl_pct_str = _get(row, "% Unrealized P/L", "Unrealized P&L %", "unrealized_pnl_pct").replace(",", "").replace("%", "").replace("+", "")
            pnl_pct = float(pnl_pct_str) if pnl_pct_str else None

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
                "currency": "USD",
                "status": "open",
                "source_ref": CSV("moomoo_telegram_sync"),
                "source_fresh_at": now.isoformat(),
                "position_hash": pos_hash,
            })
        except (ValueError, KeyError) as exc:
            logger.warning("Skipping CSV row: %s — %s", row, exc)

    return positions


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
