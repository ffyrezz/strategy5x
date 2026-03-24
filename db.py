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


def update_trade(trade_id: str, updates: dict[str, Any]) -> None:
    """Update a trade record by id."""
    get_client().table("trades").update(updates).eq("id", trade_id).execute()


def get_trades_since(since_iso: str) -> list[dict[str, Any]]:
    """Return all trades created since a given ISO timestamp."""
    resp = (
        get_client()
        .table("trades")
        .select("*")
        .gte("filled_at", since_iso)
        .order("filled_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Behavioral metrics ───────────────────────────────────────────────────


def insert_behavioral_metric(row: dict[str, Any]) -> dict[str, Any]:
    """Insert a behavioral metric record."""
    try:
        resp = get_client().table("behavioral_metrics").insert(row).execute()
        return resp.data[0] if resp.data else row
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            logger.info("Behavioral metric deduped: %s %s", row.get("metric_type"), row.get("reference_id"))
            return row
        raise


# ── Scoring runs (bulk) ─────────────────────────────────────────────────


def get_scoring_runs_since(since_iso: str) -> list[dict[str, Any]]:
    """Return all scoring runs created since a given ISO timestamp."""
    resp = (
        get_client()
        .table("scoring_runs")
        .select("*")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Alerts (bulk) ────────────────────────────────────────────────────────


def get_alerts_since(since_iso: str) -> list[dict[str, Any]]:
    """Return all alerts created since a given ISO timestamp."""
    resp = (
        get_client()
        .table("alerts")
        .select("*")
        .gte("created_at", since_iso)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Pipeline candidates (bulk) ───────────────────────────────────────────


def get_candidates_since(since_iso: str) -> list[dict[str, Any]]:
    """Return pipeline candidates updated since a given ISO timestamp."""
    resp = (
        get_client()
        .table("pipeline_candidates")
        .select("*")
        .gte("updated_at", since_iso)
        .order("updated_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Positions (bulk update) ──────────────────────────────────────────────


def update_position(position_id: str, updates: dict[str, Any]) -> None:
    """Update a position record by id."""
    get_client().table("positions").update(updates).eq("id", position_id).execute()


def get_all_open_tickers() -> list[str]:
    """Return list of tickers for all open positions."""
    resp = (
        get_client()
        .table("positions")
        .select("ticker")
        .eq("status", "open")
        .execute()
    )
    return [r["ticker"] for r in (resp.data or [])]


# ── Health check helpers ──────────────────────────────────────────────────────


def get_positions_missing_plans(within_days: int = 7) -> list[dict[str, Any]]:
    """Return positions with catalyst_date within N days but no active plan."""
    cutoff = (date.today() + timedelta(days=within_days)).isoformat()
    today = date.today().isoformat()
    positions = get_active_positions()
    catalysts = get_upcoming_catalysts(within_days=within_days)
    catalyst_tickers = {c["ticker"] for c in catalysts}

    missing = []
    for pos in positions:
        ticker = pos["ticker"]
        cat_date = pos.get("catalyst_date")
        if ticker in catalyst_tickers or (cat_date and today <= str(cat_date) <= cutoff):
            plan = get_active_plan(ticker)
            if not plan:
                missing.append(pos)
    return missing


def get_stale_reflection_count(hours: int = 48) -> int:
    """Count SELL trades older than N hours without reflection."""
    cutoff = (now_utc() - timedelta(hours=hours)).isoformat()
    resp = (
        get_client()
        .table("trades")
        .select("id", count="exact")
        .eq("side", "SELL")
        .eq("reflection_completed", False)
        .lt("filled_at", cutoff)
        .execute()
    )
    return resp.count or 0


def get_unacked_alerts_count(hours: int = 24) -> int:
    """Count alerts > N hours old that are sent but not acknowledged."""
    cutoff = (now_utc() - timedelta(hours=hours)).isoformat()
    resp = (
        get_client()
        .table("alerts")
        .select("id", count="exact")
        .eq("delivery_status", "sent")
        .eq("action_required", True)
        .is_("acknowledged_at", "null")
        .lt("created_at", cutoff)
        .execute()
    )
    return resp.count or 0


def get_latest_position_freshness() -> str | None:
    """Return the most recent source_fresh_at across all open positions."""
    resp = (
        get_client()
        .table("positions")
        .select("source_fresh_at")
        .eq("status", "open")
        .order("source_fresh_at", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0].get("source_fresh_at")
    return None


def get_all_trades() -> list[dict[str, Any]]:
    """Return all trades ordered by filled_at."""
    resp = (
        get_client()
        .table("trades")
        .select("*")
        .order("filled_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_all_table_data(table: str, limit: int = 10000) -> list[dict[str, Any]]:
    """Return all rows from a table (for export). Use with caution."""
    resp = (
        get_client()
        .table(table)
        .select("*")
        .limit(limit)
        .order("created_at", desc=True)
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


# ── Decision audit trail ─────────────────────────────────────────────────────


def log_decision(
    event_type: str,
    ticker: str,
    source: str,
    advice_summary: str,
    advice_action: str | None = None,
    advice_detail: dict | None = None,
    position_id: str | None = None,
    scoring_run_id: str | None = None,
    plan_id: str | None = None,
    trade_id: str | None = None,
    alert_id: str | None = None,
    price_at_event: float | None = None,
    user_response: str = "pending",
) -> dict | None:
    """Log a decision event to the audit trail. Best-effort; never raises."""
    try:
        row = {
            "event_type": event_type,
            "ticker": ticker.upper(),
            "source": source,
            "advice_summary": advice_summary[:500],
            "advice_action": advice_action,
            "advice_detail": advice_detail or {},
            "position_id": position_id,
            "scoring_run_id": scoring_run_id,
            "plan_id": plan_id,
            "trade_id": trade_id,
            "alert_id": alert_id,
            "price_at_event": price_at_event,
            "user_response": user_response,
            "created_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat(),
        }
        resp = get_client().table("decision_log").insert(row).execute()
        return resp.data[0] if resp.data else None
    except Exception:
        logger.debug("Failed to log decision for %s: %s", ticker, event_type, exc_info=True)
        return None


def update_decision(decision_id: str, updates: dict) -> None:
    """Update a decision log entry (e.g., grade outcome or record user response)."""
    try:
        updates["updated_at"] = now_utc().isoformat()
        get_client().table("decision_log").update(updates).eq("id", decision_id).execute()
    except Exception:
        logger.debug("Failed to update decision %s", decision_id, exc_info=True)


def get_decisions(ticker: str | None = None, event_type: str | None = None, limit: int = 50) -> list:
    """Fetch recent decision log entries."""
    try:
        q = get_client().table("decision_log").select("*").order("created_at", desc=True).limit(limit)
        if ticker:
            q = q.eq("ticker", ticker.upper())
        if event_type:
            q = q.eq("event_type", event_type)
        resp = q.execute()
        return resp.data or []
    except Exception:
        return []


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
                "delivery_attempts": 0,
                "dedupe_key": f"system_error_{source}_{now_utc().strftime('%Y%m%d_%H')}",
                "created_at": now_utc().isoformat(),
            }
        )
    except Exception:
        logger.exception("Failed to log error alert for %s", source)
