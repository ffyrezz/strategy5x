"""
Scheduled job: Sync positions from Moomoo OpenAPI or CSV.

Phase 1: CSV import from a known path.
Phase 2: OpenD API via moomoo SDK on Railway.
"""

from __future__ import annotations

import logging
from pathlib import Path

import db
from data.moomoo_sync import sync_positions_from_csv, sync_positions_from_api
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

# Default CSV path — user drops export here
CSV_PATH = Path("data/positions_export.csv")


async def run() -> None:
    """Run position sync. Tries API first, falls back to CSV."""
    logger.info("Position sync job starting")

    try:
        # Phase 2: try API first
        positions = sync_positions_from_api()

        # Phase 1 fallback: CSV
        if not positions and CSV_PATH.exists():
            logger.info("API unavailable, importing from CSV: %s", CSV_PATH)
            positions = sync_positions_from_csv(CSV_PATH)

        if not positions:
            logger.warning("No positions to sync (no API connection, no CSV found at %s)", CSV_PATH)
            db.log_error_alert("position_sync", "No position data available — check API or CSV")
            return

        # Upsert to Supabase
        db.upsert_positions(positions)
        logger.info("Synced %d positions to Supabase", len(positions))

    except Exception as exc:
        logger.error("Position sync failed: %s", exc, exc_info=True)
        db.log_error_alert("position_sync", str(exc))
