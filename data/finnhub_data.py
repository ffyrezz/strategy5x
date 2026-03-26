"""
Finnhub API wrapper for real-time price data with accurate timestamps.

Replaces yfinance for extended hours price checks. Finnhub provides:
- Real-time quotes with Unix timestamps (no stale data ambiguity)
- Pre/post market prices reflected in the current price field
- 60 requests/minute on the free tier

The timestamp lets us determine if a price is current or stale,
solving the yfinance ghost-price problem.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

import config

logger = logging.getLogger(__name__)

# Rate limiting: track last request time
_last_request_time: float = 0
_MIN_REQUEST_INTERVAL = 1.1  # seconds between requests (60/min = 1/sec, add buffer)


def _rate_limit():
    """Ensure we don't exceed Finnhub's 60 requests/minute limit."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def get_finnhub_quote(ticker: str) -> dict[str, Any]:
    """
    Fetch a real-time quote from Finnhub.

    Returns:
        {
            "ticker": str,
            "price": float | None,          # current price (includes pre/post market)
            "previous_close": float | None,
            "change": float | None,          # dollar change
            "change_pct": float | None,      # percent change
            "high": float | None,
            "low": float | None,
            "open": float | None,
            "timestamp": int,                # Unix timestamp of the quote
            "is_fresh": bool,                # True if quote is <30 minutes old
            "age_minutes": float,            # How old the quote is
        }
    """
    ticker = ticker.upper()
    api_key = getattr(config, "FINNHUB_API_KEY", None)
    if not api_key:
        logger.warning("FINNHUB_API_KEY not configured, falling back to empty result")
        return {"ticker": ticker, "price": None, "previous_close": None,
                "change": None, "change_pct": None, "timestamp": 0,
                "is_fresh": False, "age_minutes": 9999}

    _rate_limit()

    try:
        r = httpx.get(
            f"https://finnhub.io/api/v1/quote",
            params={"symbol": ticker, "token": api_key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            logger.warning("Finnhub error for %s: %s", ticker, data["error"])
            return {"ticker": ticker, "price": None, "previous_close": None,
                    "change": None, "change_pct": None, "timestamp": 0,
                    "is_fresh": False, "age_minutes": 9999}

        ts = data.get("t", 0)
        now = int(time.time())
        age_minutes = (now - ts) / 60 if ts > 0 else 9999

        return {
            "ticker": ticker,
            "price": data.get("c"),            # current price
            "previous_close": data.get("pc"),   # previous close
            "change": data.get("d"),            # dollar change
            "change_pct": data.get("dp"),       # percent change
            "high": data.get("h"),
            "low": data.get("l"),
            "open": data.get("o"),
            "timestamp": ts,
            "is_fresh": age_minutes < 30,       # <30 min = fresh
            "age_minutes": round(age_minutes, 1),
        }

    except Exception as exc:
        logger.warning("Finnhub quote failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "price": None, "previous_close": None,
                "change": None, "change_pct": None, "timestamp": 0,
                "is_fresh": False, "age_minutes": 9999}


def get_finnhub_extended_price(ticker: str) -> dict[str, Any]:
    """
    Get the best available price from Finnhub, with freshness validation.

    Unlike yfinance, Finnhub's quote 'c' field reflects the LATEST price
    including pre-market and post-market when those sessions are active.
    The timestamp tells us exactly when the price was recorded.

    Returns:
        {
            "ticker": str,
            "price": float | None,
            "previous_close": float | None,
            "change_pct": float | None,
            "timestamp": int,
            "is_fresh": bool,
            "age_minutes": float,
            "session": str,   # "market_hours", "extended", or "stale"
        }
    """
    quote = get_finnhub_quote(ticker)

    if not quote.get("price"):
        return {**quote, "session": "unknown"}

    age = quote["age_minutes"]

    # Determine session based on age
    if age < 30:
        session = "extended"  # Fresh — could be pre/post/regular
    elif age < 600:  # 10 hours
        session = "market_hours"  # Regular hours price, market closed
    else:
        session = "stale"  # Very old, something is wrong

    return {**quote, "session": session}
