"""
Configuration and constants for Strategy 5.x Growth System.
Loads secrets from environment variables, defines scoring thresholds and risk caps.
"""

import os
from datetime import timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

# ── External service credentials ──────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Timezone ──────────────────────────────────────────────────────────────────
SGT = timezone(timedelta(hours=8))  # Singapore Time (UTC+8)

# ── Scoring thresholds ────────────────────────────────────────────────────────
# SC1–SC8 are scored 0–10.  Composite = sum of all axes (max 80).
SCORING_VERSION = "sc_v0.1"
STRATEGY_VERSION = "5.3"

# Default axis weights (equal in prototype; empirical recalibration at N≥20)
AXIS_WEIGHTS: dict[str, float] = {
    "sc1": 1.0,
    "sc2": 1.0,
    "sc3": 1.0,
    "sc4": 1.0,
    "sc5": 1.0,
    "sc6": 1.0,
    "sc7": 1.0,
    "sc8": 1.0,
}

# Conviction buckets based on composite score (sum, not average)
CONVICTION_BUCKETS: list[tuple[float, str]] = [
    (64.0, "A"),  # ≥64 → A (strong conviction)
    (48.0, "B"),  # ≥48 → B (moderate)
    (32.0, "C"),  # ≥32 → C (weak)
    (0.0, "D"),   # <32 → D (avoid)
]

# Minimum composite score for ENTRY_READY verdict
MIN_ENTRY_SCORE: float = 48.0  # bucket B or above

# ── Concentration / risk caps ─────────────────────────────────────────────────
SINGLE_NAME_CAP_PCT: float = 10.0        # max 10% of portfolio in one name
BINARY_EXPOSURE_CAP_PCT: float = 10.0    # max 10% in binary-catalyst positions
MARGIN_UTIL_CAP_PCT: float = 40.0        # max 40% margin utilization
MAX_OPEN_POSITIONS: int = 15
CASH_RUNWAY_CAUTION_MONTHS: int = 12
CASH_RUNWAY_BLOCK_MONTHS: int = 6

# ── Data freshness thresholds ─────────────────────────────────────────────────
POSITION_STALE_MINUTES: int = 60         # warn if older than 60 min
PRICE_CACHE_SECONDS: int = 900           # 15-minute cache for yfinance

# ── Alert settings ────────────────────────────────────────────────────────────
CATALYST_ALERT_DAYS: list[int] = [7, 3, 1]  # T-7, T-3, T-1
PRICE_MOVE_THRESHOLD_PCT: float = 10.0       # alert on >10% move
FALSE_NEGATIVE_THRESHOLD_PCT: float = 25.0   # flag if rejected ticker moves >25%
FALSE_NEGATIVE_TRACKING_DAYS: int = 30

# ── Overnight quiet hours (SGT) ──────────────────────────────────────────────
QUIET_HOURS_START: int = 0   # 00:00 SGT
QUIET_HOURS_END: int = 6     # 06:00 SGT
MAX_QUIET_HOUR_LINES: int = 5  # 3 AM design: max 5 lines per message

# ── Moomoo OpenAPI (Phase 2 — live position sync) ────────────────────────────
MOOMOO_ENABLED: bool = os.environ.get("MOOMOO_ENABLED", "false").lower() == "true"
MOOMOO_OPEND_HOST: str = os.environ.get("MOOMOO_OPEND_HOST", "127.0.0.1")
MOOMOO_OPEND_PORT: int = int(os.environ.get("MOOMOO_OPEND_PORT", "11111"))
MOOMOO_TRADE_ENV: str = os.environ.get("MOOMOO_TRADE_ENV", "REAL")  # REAL or SIMULATE
MOOMOO_MARKET: str = "US"  # US market only for now

# ── Finnhub API (real-time quotes with timestamps) ─────────────────────────
FINNHUB_API_KEY: str = os.environ.get("FINNHUB_API_KEY", "")

# ── AI Dissent (feature-flagged) ──────────────────────────────────────────────
AI_DISSENT_ENABLED: bool = os.environ.get("AI_DISSENT_ENABLED", "false").lower() == "true"
PERPLEXITY_API_KEY: str = os.environ.get("PERPLEXITY_API_KEY", "")
AI_DISSENT_MODEL: str = "sonar"
AI_DISSENT_MAX_MONTHLY_COST_USD: float = 10.0

# ── FDA approval base rates (default lookups) ────────────────────────────────
FDA_BASE_RATES: dict[str, float] = {
    "NDA": 0.90,
    "BLA": 0.85,
    "sNDA": 0.92,
    "PDUFA": 0.85,
    "CRL_RESPONSE": 0.60,
    "PHASE3_READOUT": 0.58,
    "ADCOM": 0.75,
    "DEFAULT": 0.68,
}
