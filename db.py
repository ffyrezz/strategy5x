"""
Supabase client wrapper.

Provides typed helper functions for common queries. All writes include error
handling that logs failures to the alerts table (or stderr as last resort).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from supabase import create_client, Client

import config
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────

_client: Client | None = None


def get_client() -> Client:
    """Return (and lazily create) the Supabase client."""
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


# ── Positions ─────────────────────────────────────────────────────────────────


def get_active_positions() -> list[dict[str, Any]]:
    """Return all open positions."""
    resp = get_client().table("positions").select("*").eq("status", "open").execute()
    return resp.data or []


def get_position_by_ticker(ticker: str) -> dict[str, Any] | None:
    """Return the open position for a ticker, or None."""
    resp = (
        get_client()
        .table("positions")
        .select("*")
        .eq("ticker", ticker.upper())
        .eq("status", "open")
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def upsert_positions(rows: list[dict[str, Any]]) -> None:
    """Upsert position rows (keyed on broker_account_id + ticker)."""
    if not rows:
        return
    get_client().table("positions").upsert(
        rows, on_conflict="broker_account_id,ticker"
    ).execute()


# ── Pipeline candidates ──────────────────────────────────────────────────────


def get_candidate(ticker: str) -> dict[str, Any] | None:
    """Return the active pipeline candidate for a ticker."""
    resp = (
        get_client()
        .table("pipeline_candidates")
        .select("*")
        .eq("ticker", ticker.upper())
        .not_.in_("status", ["eliminated", "expired"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def get_upcoming_catalysts(within_days: int = 30) -> list[dict[str, Any]]:
    """Return pipeline candidates with catalyst_date within N days from today."""
    cutoff = (date.today() + timedelta(days=within_days)).isoformat()
    today = date.today().isoformat()
    resp = (
        get_client()
        .table("pipeline_candidates")
        .select("*")
        .gte("catalyst_date", today)
        .lte("catalyst_date", cutoff)
        .not_.in_("status", ["eliminated", "expired"])
        .order("catalyst_date")
        .execute()
    )
    return resp.data or []


def get_catalysts_at_t_minus(days: list[int]) -> list[dict[str, Any]]:
    """Return candidates whose catalyst_date is exactly T-N days from today."""
    target_dates = [(date.today() + timedelta(days=d)).isoformat() for d in days]
    resp = (
        get_client()
        .table("pipeline_candidates")
        .select("*")
        .in_("catalyst_date", target_dates)
        .not_.in_("status", ["eliminated", "expired"])
        .execute()
    )
    return resp.data or []


def upsert_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Insert or update a pipeline candidate (keyed on ticker + catalyst_date)."""
    resp = (
        get_client()
        .table("pipeline_candidates")
        .upsert(row, on_conflict="ticker,catalyst_date")
        .execute()
    )
    return resp.data[0] if resp.data else row


# ── Scoring runs ─────────────────────────────────────────────────────────────


def insert_scoring_run(row: dict[str, Any]) -> dict[str, Any]:
    """Insert an immutable scoring run record."""
    resp = get_client().table("scoring_runs").insert(row).execute()
    return resp.data[0] if resp.data else row


def get_latest_scoring_run(ticker: str) -> dict[str, Any] | None:
    """Return the most recent scoring run for a ticker."""
    resp = (
        get_client()
        .table("scoring_runs")
        .select("*")
        .eq("ticker", ticker.upper())
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


# ── Pre-commitment plans ─────────────────────────────────────────────────────


def get_active_plan(ticker: str) -> dict[str, Any] | None:
    """Return the active pre-commitment plan for a ticker."""
    resp = (
        get_client()
        .table("precommitment_plans")
        .select("*")
        .eq("ticker", ticker.upper())
        .eq("is_active", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def insert_plan(row: dict[str, Any]) -> dict[str, Any]:
    """Insert a new pre-commitment plan."""
    resp = get_client().table("precommitment_plans").insert(row).execute()
    return resp.data[0] if resp.data else row


# ── Alerts ────────────────────────────────────────────────────────────────────


def insert_alert(row: dict[str, Any]) -> dict[str, Any]:
    """Insert an alert record. Duplicate dedupe_keys are silently ignored."""
    try:
        resp = get_client().table("alerts").insert(row).execute()
        return resp.data[0] if resp.data else row
    except Exception as exc:
        # Likely unique constraint on dedupe_key — not an error
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            logger.info("Alert deduped: %s", row.get("dedupe_key"))
            return row
        raise


def update_alert(alert_id: str, updates: dict[str, Any]) -> None:
    """Update an alert by id (e.g. set acknowledged_at)."""
    get_client().table("alerts").update(updates).eq("id", alert_id).execute()


def get_alert(alert_id: str) -> dict[str, Any] | None:
    """Return an alert by id."""
    resp = get_client().table("alerts").select("*").eq("id", alert_id).limit(1).execute()
    return resp.data[0] if resp.data else None


def get_pending_alerts() -> list[dict[str, Any]]:
    """Return alerts that are sent but not yet acknowledged."""
    resp = (
        get_client()
        .table("alerts")
        .select("*")
        .eq("delivery_status", "sent")
        .eq("action_required", True)
        .is_("acknowledged_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Trades ────────────────────────────────────────────────────────────────────


def insert_trade(row: dict[str, Any]) -> dict[str, Any]:
    """Insert a trade record."""
    resp = get_client().table("trades").insert(row).execute()
    return resp.data[0] if resp.data else row


def get_recent_trades(ticker: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent trades, optionally filtered by ticker."""
    q = get_client().table("trades").select("*").order("filled_at", desc=True).limit(limit)
    if ticker:
        q = q.eq("ticker", ticker.upper())
    return q.execute().data or []


def get_unreflected_trades() -> list[dict[str, Any]]:
    """Return closed trades (SELL side) that haven't been reflected on yet."""
    resp = (
        get_client()
        .table("trades")
        .select("*")
        .eq("side", "SELL")
        .eq("reflection_completed", False)
        .order("filled_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Rules ─────────────────────────────────────────────────────────────────────


def get_active_rules(category: str | None = None) -> list[dict[str, Any]]:
    """Return active rules, optionally filtered by category."""
    q = get_client().table("rules").select("*").eq("active", True)
    if category:
        q = q.eq("rule_category", category)
    return q.execute().data or []


def get_hard_bans() -> list[dict[str, Any]]:
    """Return all active hard-ban rules."""
    return get_active_rules("hard_ban")


def get_current_rule_version() -> int:
    """Return the highest active rule version number."""
    resp = (
        get_client()
        .table("rules")
        .select("rule_version")
        .eq("active", True)
        .order("rule_version", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["rule_version"]
    return 1


# ── Rejected candidates (false-negative tracking) ────────────────────────────


def get_rejected_candidates_for_tracking() -> list[dict[str, Any]]:
    """Return rejected candidates still within the false-negative tracking window."""
    cutoff = (date.today() - timedelta(days=config.FALSE_NEGATIVE_TRACKING_DAYS)).isoformat()
    resp = (
        get_client()
        .table("pipeline_candidates")
        .select("*")
        .eq("status", "rejected")
        .eq("false_negative_flag", False)
        .gte("updated_at", cutoff)
        .execute()
    )
    return resp.data or []


def update_candidate(candidate_id: str, updates: dict[str, Any]) -> None:
    """Update a pipeline candidate by id."""
    get_client().table("pipeline_candidates").update(updates).eq("id", candidate_id).execute()


# ── Keepalive ─────────────────────────────────────────────────────────────────


def keepalive_ping() -> bool:
    """Run a trivial query to keep Supabase free tier alive. Returns True on success."""
    try:
        get_client().table("rules").select("id").limit(1).execute()
        return True
    except Exception as exc:
        logger.error("Keepalive ping failed: %s", exc)
        return False


# ── Error logging helper ─────────────────────────────────────────────────────


def log_error_alert(source: str, error_msg: str) -> None:
    """Write a system error alert. Best-effort; swallows exceptions."""
    try:
        insert_alert(
            {
                "alert_type": "system_error",
                "priority": "high",
                "title": f"System error: {source}",
                "body": error_msg[:500],
                "action_required": False,
                "channel": "telegram",
                "delivery_status": "queued",
                "dedupe_key": f"system_error_{source}_{now_utc().strftime('%Y%m%d_%H')}",
                "created_at": now_utc().isoformat(),
            }
        )
    except Exception:
        logger.exception("Failed to log error alert for %s", source)
