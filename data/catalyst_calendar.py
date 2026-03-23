"""
Catalyst calendar data source.

Phase 1: manual entry via /candidate command.
Phase 2: BiopharmCatalyst API integration.

For now this module provides helpers for working with catalyst dates
already stored in pipeline_candidates.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import db

logger = logging.getLogger(__name__)


def get_catalysts_within(days: int = 30) -> list[dict[str, Any]]:
    """Return pipeline candidates with catalysts within N days."""
    return db.get_upcoming_catalysts(within_days=days)


def get_catalysts_at_countdown(t_minus_days: list[int]) -> list[dict[str, Any]]:
    """
    Return candidates whose catalyst is exactly T-N days away.

    t_minus_days: e.g. [7, 3, 1] for T-7, T-3, T-1
    """
    return db.get_catalysts_at_t_minus(t_minus_days)


def days_until_catalyst(catalyst_date: date | str | None) -> int | None:
    """Calculate days from today until catalyst date."""
    if catalyst_date is None:
        return None
    if isinstance(catalyst_date, str):
        try:
            catalyst_date = date.fromisoformat(catalyst_date)
        except ValueError:
            return None
    return (catalyst_date - date.today()).days


def format_countdown(days: int | None) -> str:
    """Format a countdown as T-N string."""
    if days is None:
        return "T-?"
    if days == 0:
        return "T-0 (TODAY)"
    if days < 0:
        return f"T+{abs(days)} (PASSED)"
    return f"T-{days}"


# TODO: Phase 2 — BiopharmCatalyst API integration
# def fetch_pdufa_calendar() -> list[dict]:
#     """Fetch upcoming PDUFA dates from BiopharmCatalyst."""
#     pass
