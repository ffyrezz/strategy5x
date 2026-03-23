"""
Moomoo OpenAPI integration stub.

Phase 1: CSV import fallback.
Phase 2: Live OpenD connection via moomoo Python SDK on Railway.

This module provides the interface that position_sync.py calls.
In Phase 1, it reads from a CSV file. In Phase 2, it connects to OpenD.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.provenance import CSV, FINANCE
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


def sync_positions_from_csv(csv_path: str | Path) -> list[dict[str, Any]]:
    """
    Parse positions from a Moomoo CSV export.

    Expected CSV columns: Symbol, Name, Qty, Avg Cost, Last Price, Market Value,
                          Unrealized P&L, Unrealized P&L %

    Returns list of dicts matching the positions table schema.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return []

    positions = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ticker = row.get("Symbol", "").strip().upper()
                if not ticker:
                    continue

                qty = float(row.get("Qty", 0))
                avg_cost = float(row.get("Avg Cost", 0))
                last_price = float(row.get("Last Price", 0)) or None
                market_value = float(row.get("Market Value", 0)) or None

                # Compute position hash for change detection
                hash_input = json.dumps({"ticker": ticker, "qty": qty, "avg_cost": avg_cost, "last_price": last_price})
                pos_hash = f"sha256:{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

                positions.append({
                    "broker_account_id": "csv_import",
                    "ticker": ticker,
                    "security_name": row.get("Name", "").strip() or None,
                    "asset_type": "equity",
                    "quantity": qty,
                    "avg_cost": avg_cost,
                    "last_price": last_price,
                    "market_value": market_value,
                    "unrealized_pnl": float(row.get("Unrealized P&L", 0)) or None,
                    "unrealized_pnl_pct": float(row.get("Unrealized P&L %", "0").replace("%", "")) if row.get("Unrealized P&L %") else None,
                    "currency": "USD",
                    "status": "open",
                    "source_ref": CSV("moomoo_export"),
                    "source_fresh_at": now_utc().isoformat(),
                    "position_hash": pos_hash,
                    "updated_at": now_utc().isoformat(),
                })
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping CSV row: %s — %s", row, exc)

    logger.info("Parsed %d positions from CSV", len(positions))
    return positions


def sync_positions_from_api() -> list[dict[str, Any]]:
    """
    Sync positions from Moomoo OpenAPI via OpenD.

    Phase 2 stub — returns empty list. When implemented, this will:
    1. Connect to OpenD on Railway
    2. Call get_positions() via moomoo SDK
    3. Return positions in the same format as sync_positions_from_csv
    """
    # TODO: Phase 2 — implement Moomoo OpenAPI sync
    # from moomoo import OpenSecTradeContext, TrdEnv, TrdMarket
    # ctx = OpenSecTradeContext(host='opend-host', port=11111, ...)
    # ret, positions = ctx.position_list_query(trd_env=TrdEnv.REAL)
    logger.info("Moomoo API sync not yet implemented — use CSV import")
    return []
