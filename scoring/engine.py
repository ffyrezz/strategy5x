"""
Deterministic scoring engine for SC1–SC8.

SC1 (Catalyst Timing), SC5 (Going Concern), SC6 (Liquidity), SC7 (Risk/Reward)
are fully deterministic — computed from structured data.

SC2 (Clinical Data), SC3 (Unmet Need), SC4 (Competitive Landscape),
SC8 (Macro/Sector) are hybrid — return None in Phase 1, awaiting AI integration.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any

import config
from scoring.constants import SC1_CURVE, SC5_CURVE, SC6_CURVE, SC7_CURVE

logger = logging.getLogger(__name__)


# ── Curve lookup helper ──────────────────────────────────────────────────────


def _lookup_curve(value: float, curve: list[tuple[float, float]]) -> float:
    """Walk a sorted (max_threshold, score) curve and return the first match."""
    for threshold, score in curve:
        if value <= threshold:
            return score
    return curve[-1][1]  # fallback to last entry


# ── Individual axis scorers ──────────────────────────────────────────────────


def score_sc1(catalyst_date: date | None) -> dict[str, Any]:
    """SC1: Catalyst Timing. Score based on days until event."""
    if catalyst_date is None:
        return {"score": None, "method": "deterministic", "components": {"days_to_event": None}}

    days = (catalyst_date - date.today()).days
    if days < 0:
        # Catalyst already passed
        return {"score": None, "method": "deterministic", "components": {"days_to_event": days}}

    score = _lookup_curve(days, SC1_CURVE)
    return {"score": score, "method": "deterministic", "components": {"days_to_event": days}}


def score_sc5(cash_runway_months: float | None) -> dict[str, Any]:
    """SC5: Going Concern / Financial Health. Score based on cash runway."""
    if cash_runway_months is None:
        return {"score": None, "method": "deterministic", "components": {"cash_runway_months": None}}

    score = _lookup_curve(cash_runway_months, SC5_CURVE)
    return {"score": score, "method": "deterministic", "components": {"cash_runway_months": cash_runway_months}}


def score_sc6(adv_30d_usd: float | None) -> dict[str, Any]:
    """SC6: Liquidity / Tradability. Score based on 30-day average daily volume in USD."""
    if adv_30d_usd is None:
        return {"score": None, "method": "deterministic", "components": {"adv30_usd": None}}

    score = _lookup_curve(adv_30d_usd, SC6_CURVE)
    return {"score": score, "method": "deterministic", "components": {"adv30_usd": adv_30d_usd}}


def score_sc7(upside_pct: float | None, downside_pct: float | None) -> dict[str, Any]:
    """SC7: Risk/Reward Ratio. Score based on upside/downside ratio."""
    if upside_pct is None or downside_pct is None or downside_pct == 0:
        return {
            "score": None,
            "method": "deterministic",
            "components": {"upside_pct": upside_pct, "downside_pct": downside_pct, "ratio": None},
        }

    ratio = abs(upside_pct / downside_pct)
    score = _lookup_curve(ratio, SC7_CURVE)
    return {
        "score": score,
        "method": "deterministic",
        "components": {"upside_pct": upside_pct, "downside_pct": downside_pct, "ratio": round(ratio, 2)},
    }


def score_sc2_stub() -> dict[str, Any]:
    """SC2: Clinical Data Strength. Stub — requires AI or manual input."""
    return {"score": None, "method": "hybrid", "components": {"note": "manual_or_ai_required"}}


def score_sc3_stub() -> dict[str, Any]:
    """SC3: Unmet Medical Need. Stub — requires AI or manual input."""
    return {"score": None, "method": "hybrid", "components": {"note": "manual_or_ai_required"}}


def score_sc4_stub() -> dict[str, Any]:
    """SC4: Competitive Landscape. Stub — requires AI or manual input."""
    return {"score": None, "method": "hybrid", "components": {"note": "manual_or_ai_required"}}


def score_sc8() -> dict[str, Any]:
    """
    SC8: Macro/Sector Alignment.

    Uses XBI (biotech ETF) and VIX to gauge sector conditions.
    Start at 5, +2 if XBI > 50DMA, +1 if XBI 20d return > 5%,
    -1 if VIX > 25, -2 if XBI 20d return < -8%. Clamp 0-10.
    """
    from data.market_data import get_sector_macro_data

    data = get_sector_macro_data()
    xbi_price = data.get("xbi_price")
    xbi_50dma = data.get("xbi_50dma")
    xbi_20d_ret = data.get("xbi_20d_return_pct")
    vix = data.get("vix")

    # Need at least some data to score
    if xbi_price is None and vix is None:
        return {"score": None, "method": "deterministic", "components": data}

    score = 5.0

    if xbi_price is not None and xbi_50dma is not None and xbi_price > xbi_50dma:
        score += 2

    if xbi_20d_ret is not None and xbi_20d_ret > 5:
        score += 1

    if vix is not None and vix > 25:
        score -= 1

    if xbi_20d_ret is not None and xbi_20d_ret < -8:
        score -= 2

    score = max(0.0, min(10.0, score))

    return {
        "score": score,
        "method": "deterministic",
        "components": {
            "xbi_price": xbi_price,
            "xbi_50dma": xbi_50dma,
            "xbi_20d_return_pct": xbi_20d_ret,
            "vix": vix,
            "base": 5,
            "adjustments": score - 5,
        },
    }


# ── Composite scoring ────────────────────────────────────────────────────────


def compute_composite(axes: dict[str, dict[str, Any]]) -> tuple[float | None, str]:
    """
    Compute weighted composite score from axis results.

    Returns (composite_score, conviction_bucket).
    If fewer than 4 deterministic axes have scores, returns (None, "INCOMPLETE").
    """
    total = 0.0
    scored_count = 0

    for axis_key, axis_data in axes.items():
        s = axis_data.get("score")
        if s is not None:
            weight = config.AXIS_WEIGHTS.get(axis_key, 1.0)
            total += s * weight
            scored_count += 1

    if scored_count < 2:
        return None, "INCOMPLETE"

    # Determine conviction bucket
    bucket = "D"
    for threshold, label in config.CONVICTION_BUCKETS:
        if total >= threshold:
            bucket = label
            break

    return round(total, 2), bucket


def compute_verdict(composite: float | None, bucket: str) -> tuple[str, str]:
    """
    Determine verdict from composite score.

    Returns (verdict, verdict_reason).
    """
    if composite is None:
        return "monitor", "Insufficient data for full scoring"
    if composite >= config.MIN_ENTRY_SCORE:
        return "entry_ready", f"Composite {composite}, bucket {bucket}"
    return "watch", f"Composite {composite} below entry threshold {config.MIN_ENTRY_SCORE}"


def build_input_hash(input_data: dict[str, Any]) -> str:
    """SHA-256 hash of input data for idempotency verification."""
    serialized = json.dumps(input_data, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"


def run_scoring(
    ticker: str,
    catalyst_date: date | None = None,
    cash_runway_months: float | None = None,
    adv_30d_usd: float | None = None,
    upside_pct: float | None = None,
    downside_pct: float | None = None,
    current_price: float | None = None,
    manual_scores: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Run a full scoring pass for a ticker.

    Returns a dict matching the scoring_runs table schema.
    manual_scores: optional dict like {"sc2": 7.0, "sc3": 6.0} for user-provided axes.
    """
    manual_scores = manual_scores or {}

    # Score each axis
    axes = {
        "sc1": score_sc1(catalyst_date),
        "sc2": {"score": manual_scores.get("sc2"), "method": "hybrid", "components": {"source": "manual"}} if "sc2" in manual_scores else score_sc2_stub(),
        "sc3": {"score": manual_scores.get("sc3"), "method": "hybrid", "components": {"source": "manual"}} if "sc3" in manual_scores else score_sc3_stub(),
        "sc4": {"score": manual_scores.get("sc4"), "method": "hybrid", "components": {"source": "manual"}} if "sc4" in manual_scores else score_sc4_stub(),
        "sc5": score_sc5(cash_runway_months),
        "sc6": score_sc6(adv_30d_usd),
        "sc7": score_sc7(upside_pct, downside_pct),
        "sc8": {"score": manual_scores.get("sc8"), "method": "hybrid", "components": {"source": "manual"}} if "sc8" in manual_scores else score_sc8(),
    }

    composite, bucket = compute_composite(axes)
    verdict, verdict_reason = compute_verdict(composite, bucket)

    # Build input snapshot for provenance
    input_data = {
        "ticker": ticker,
        "catalyst_date": str(catalyst_date) if catalyst_date else None,
        "cash_runway_months": cash_runway_months,
        "adv_30d_usd": adv_30d_usd,
        "upside_pct": upside_pct,
        "downside_pct": downside_pct,
        "current_price": current_price,
        "manual_scores": manual_scores,
    }

    # Determine scoring method label
    has_manual = any(k.startswith("sc") and k in manual_scores for k in ["sc2", "sc3", "sc4", "sc8"])
    scoring_method = "hybrid" if has_manual else "deterministic"

    # Build data_sources provenance
    data_sources = {}
    for key, axis_data in axes.items():
        if axis_data["method"] == "deterministic":
            data_sources[key] = "[CALC]"
        elif axis_data.get("components", {}).get("source") == "manual":
            data_sources[key] = "[MANUAL]"
        else:
            data_sources[key] = "[PENDING]"

    now_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    return {
        "ticker": ticker.upper(),
        "run_type": "manual",
        "strategy_version": config.STRATEGY_VERSION,
        "rule_version": 1,  # will be overridden by caller with actual version
        "playbook": "A",     # default; overridden by caller
        "input_data": input_data,
        "input_price": current_price,
        "sc1": axes["sc1"]["score"],
        "sc2": axes["sc2"]["score"],
        "sc3": axes["sc3"]["score"],
        "sc4": axes["sc4"]["score"],
        "sc5": axes["sc5"]["score"],
        "sc6": axes["sc6"]["score"],
        "sc7": axes["sc7"]["score"],
        "sc8": axes["sc8"]["score"],
        "composite_score": composite,
        "scoring_method": scoring_method,
        "data_sources": data_sources,
        "bear_summary": "Deterministic DA checks pending",  # NOT NULL — filled by DA
        "da_verdict": "PROCEED",
        "da_details": {},
        "da_override": False,
        "invalidation_conditions": [],
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "portfolio_context": {},  # filled by caller
        "run_status": "complete",
        "idempotency_key": f"{ticker.upper()}_manual_{now_str}",
        # axes detail stored in input_data jsonb
        "_axes_detail": axes,
    }
