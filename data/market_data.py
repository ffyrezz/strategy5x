"""
yfinance wrapper for price data.

Caches results for 15 minutes to avoid rate limits.
All returned values carry provenance tag [FINANCE].
"""

from __future__ import annotations

import logging
import time
from typing import Any

import yfinance as yf

import config
from utils.provenance import FINANCE

logger = logging.getLogger(__name__)

# Simple in-memory cache: {ticker: (timestamp, data)}
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _is_cached(ticker: str) -> bool:
    """Check if cached data is still fresh."""
    if ticker not in _cache:
        return False
    cached_at, _ = _cache[ticker]
    return (time.time() - cached_at) < config.PRICE_CACHE_SECONDS


def get_price_data(ticker: str) -> dict[str, Any]:
    """
    Fetch current price, volume, and basic info for a ticker.

    Returns:
        {
            "ticker": str,
            "price": float | None,
            "previous_close": float | None,
            "change_pct": float | None,
            "volume": int | None,
            "avg_volume_30d": int | None,
            "adv_30d_usd": float | None,
            "market_cap": float | None,
            "name": str | None,
            "pre_market_price": float | None,
            "post_market_price": float | None,
            "provenance": str,
        }
    """
    ticker = ticker.upper()

    if _is_cached(ticker):
        return _cache[ticker][1]

    result: dict[str, Any] = {
        "ticker": ticker,
        "price": None,
        "previous_close": None,
        "change_pct": None,
        "volume": None,
        "avg_volume_30d": None,
        "adv_30d_usd": None,
        "market_cap": None,
        "name": None,
        "pre_market_price": None,
        "post_market_price": None,
        "provenance": FINANCE("yfinance"),
    }

    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        avg_vol = info.get("averageDailyVolume10Day") or info.get("averageVolume")

        result["price"] = float(price) if price else None
        result["previous_close"] = float(prev_close) if prev_close else None
        result["volume"] = int(info.get("volume", 0)) or None
        result["avg_volume_30d"] = int(avg_vol) if avg_vol else None
        result["market_cap"] = float(info.get("marketCap", 0)) or None
        result["name"] = info.get("shortName") or info.get("longName")

        # Extended hours prices
        pre_price = info.get("preMarketPrice")
        post_price = info.get("postMarketPrice")
        if pre_price:
            result["pre_market_price"] = float(pre_price)
        if post_price:
            result["post_market_price"] = float(post_price)

        # Compute derived values
        if result["price"] and result["previous_close"]:
            result["change_pct"] = round(
                ((result["price"] - result["previous_close"]) / result["previous_close"]) * 100, 2
            )

        if result["avg_volume_30d"] and result["price"]:
            result["adv_30d_usd"] = result["avg_volume_30d"] * result["price"]

    except Exception as exc:
        logger.warning("yfinance error for %s: %s", ticker, exc)

    _cache[ticker] = (time.time(), result)
    return result


def get_extended_hours_price(ticker: str) -> dict[str, Any]:
    """
    Get the best available price including pre/post market.

    Returns:
        {
            "ticker": str,
            "price": float | None,       # best available (extended or regular)
            "regular_price": float | None,
            "pre_market_price": float | None,
            "post_market_price": float | None,
            "is_extended_hours": bool,
            "session": str,              # "pre_market", "post_market", or "regular"
        }
    """
    data = get_price_data(ticker)

    result: dict[str, Any] = {
        "ticker": ticker.upper(),
        "price": data.get("price"),
        "regular_price": data.get("price"),
        "pre_market_price": data.get("pre_market_price"),
        "post_market_price": data.get("post_market_price"),
        "is_extended_hours": False,
        "session": "regular",
    }

    # Prefer pre-market price if available (most relevant for PDUFA overnight results)
    if data.get("pre_market_price"):
        result["price"] = data["pre_market_price"]
        result["is_extended_hours"] = True
        result["session"] = "pre_market"
    elif data.get("post_market_price"):
        result["price"] = data["post_market_price"]
        result["is_extended_hours"] = True
        result["session"] = "post_market"

    return result


def get_bulk_prices(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch price data for multiple tickers."""
    return {t: get_price_data(t) for t in tickers}


def get_cash_runway_months(ticker: str) -> float | None:
    """
    Estimate cash runway in months from yfinance financials.

    Uses: total_cash / abs(quarterly_operating_cashflow) * 3
    Returns None if data unavailable.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info or {}
        total_cash = info.get("totalCash")
        op_cashflow = info.get("operatingCashflow")

        if total_cash and op_cashflow and op_cashflow < 0:
            # quarterly burn rate → months
            quarterly_burn = abs(op_cashflow)
            monthly_burn = quarterly_burn / 3
            if monthly_burn > 0:
                return round(total_cash / monthly_burn, 1)
    except Exception as exc:
        logger.warning("Cash runway calc failed for %s: %s", ticker, exc)

    return None


def get_analyst_targets(ticker: str) -> dict[str, float | None]:
    """
    Fetch analyst price targets for R:R calculation.

    Returns {"target_high": float, "target_low": float, "target_mean": float, "current": float}
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info or {}
        return {
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "target_mean": info.get("targetMeanPrice"),
            "current": info.get("currentPrice") or info.get("regularMarketPrice"),
        }
    except Exception as exc:
        logger.warning("Analyst targets failed for %s: %s", ticker, exc)
        return {"target_high": None, "target_low": None, "target_mean": None, "current": None}


def get_sector_macro_data() -> dict[str, Any]:
    """
    Fetch XBI and VIX data for SC8 scoring.

    Returns:
        {
            "xbi_price": float | None,
            "xbi_50dma": float | None,
            "xbi_20d_return_pct": float | None,
            "vix": float | None,
            "provenance": str,
        }
    """
    cache_key = "_sector_macro"
    if _is_cached(cache_key):
        return _cache[cache_key][1]

    result: dict[str, Any] = {
        "xbi_price": None,
        "xbi_50dma": None,
        "xbi_20d_return_pct": None,
        "vix": None,
        "provenance": FINANCE("yfinance"),
    }

    try:
        xbi = yf.Ticker("XBI")
        hist = xbi.history(period="3mo")
        if len(hist) >= 50:
            result["xbi_price"] = float(hist["Close"].iloc[-1])
            result["xbi_50dma"] = float(hist["Close"].rolling(50).mean().iloc[-1])
        elif len(hist) >= 20:
            result["xbi_price"] = float(hist["Close"].iloc[-1])

        if len(hist) >= 20:
            close_now = float(hist["Close"].iloc[-1])
            close_20d_ago = float(hist["Close"].iloc[-20])
            if close_20d_ago > 0:
                result["xbi_20d_return_pct"] = round(
                    ((close_now - close_20d_ago) / close_20d_ago) * 100, 2
                )
    except Exception as exc:
        logger.warning("XBI data fetch failed: %s", exc)

    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="5d")
        if len(vix_hist) > 0:
            result["vix"] = float(vix_hist["Close"].iloc[-1])
    except Exception as exc:
        logger.warning("VIX data fetch failed: %s", exc)

    _cache[cache_key] = (time.time(), result)
    return result


def clear_cache() -> None:
    """Clear the price cache."""
    _cache.clear()
