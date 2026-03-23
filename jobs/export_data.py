"""
Track 4 fallback export — Dump all Supabase tables to CSV files.

Can be triggered via /export command or run as `python -m jobs.export_data`.
Saves files to a timestamped directory under exports/.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import db
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("exports")

TABLES_TO_EXPORT = [
    ("positions", None),
    ("trades", None),
    ("scoring_runs", None),
    ("pipeline_candidates", None),
    ("precommitment_plans", None),
    ("behavioral_metrics", None),
    ("alerts", 90),  # last 90 days only
]


def _export_table(table_name: str, output_dir: Path, days_limit: int | None = None) -> int:
    """Export a single table to CSV. Returns row count."""
    if days_limit:
        cutoff = (now_utc() - timedelta(days=days_limit)).isoformat()
        resp = (
            db.get_client()
            .table(table_name)
            .select("*")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(10000)
            .execute()
        )
    else:
        resp = db.get_all_table_data(table_name)
        # get_all_table_data returns list, not response
        if isinstance(resp, list):
            rows = resp
        else:
            rows = resp.data or []

    if isinstance(resp, list):
        rows = resp
    else:
        rows = resp.data or [] if hasattr(resp, 'data') else resp

    if not rows:
        return 0

    csv_path = output_dir / f"{table_name}.csv"
    fieldnames = list(rows[0].keys())

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Convert complex types to strings for CSV
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    import json
                    clean_row[k] = json.dumps(v)
                else:
                    clean_row[k] = v
            writer.writerow(clean_row)

    return len(rows)


def run_export() -> tuple[Path, dict[str, int]]:
    """
    Export all tables to CSV in a timestamped directory.

    Returns (export_dir, {table_name: row_count}).
    """
    now = now_utc()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    output_dir = EXPORT_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for table_name, days_limit in TABLES_TO_EXPORT:
        try:
            count = _export_table(table_name, output_dir, days_limit)
            results[table_name] = count
            logger.info("Exported %s: %d rows", table_name, count)
        except Exception as exc:
            logger.error("Failed to export %s: %s", table_name, exc)
            results[table_name] = -1

    return output_dir, results


def format_export_summary(export_dir: Path, results: dict[str, int]) -> str:
    """Format export results as a human-readable summary."""
    lines = [f"Data export complete: {export_dir}"]
    lines.append("")
    total = 0
    for table, count in results.items():
        if count < 0:
            lines.append(f"  {table}: FAILED")
        else:
            lines.append(f"  {table}: {count} rows")
            total += count
    lines.append(f"\nTotal: {total} rows across {len(results)} tables")
    return "\n".join(lines)


async def run() -> None:
    """Async entry point for scheduler."""
    export_dir, results = run_export()
    logger.info("Export complete: %s", export_dir)


def main() -> None:
    """Entry point for CLI: python -m jobs.export_data"""
    logging.basicConfig(level=logging.INFO)
    export_dir, results = run_export()
    print(format_export_summary(export_dir, results))


if __name__ == "__main__":
    main()
