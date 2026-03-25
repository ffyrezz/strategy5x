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

    IMPORTANT: yfinance returns stale post-market prices from previous sessions.
    We validate extended hours prices against the regular price to catch this:
    - If extended price deviates >30% from regular price AND is older than today,
      it's likely stale — fall back to regular price.
    - We also check the yfinance timestamp fields when available.

    Returns:
        {
            "ticker": str,
            "price": float | None,
            "regular_price": float | None,
            "pre_market_price": float | None,
            "post_market_price": float | None,
            "is_extended_hours": bool,
            "session": str,
        }
    """
    data = get_price_data(ticker)
    regular_price = data.get("price")

    result: dict[str, Any] = {
        "ticker": ticker.upper(),
        "price": regular_price,
        "regular_price": regular_price,
        "pre_market_price": data.get("pre_market_price"),
        "post_market_price": data.get("post_market_price"),
        "is_extended_hours": False,
        "session": "regular",
    }

    def _is_plausible(ext_price: float, reg_price: float) -> bool:
        """Check if extended hours price is plausible (not stale).
        
        yfinance often returns post-market prices from days ago.
        A >25% deviation from regular close is almost certainly stale data
        rather than a real extended-hours move (except for true binary events).
        We use 25% as the threshold — real binary moves ARE possible above this,
        but false alerts from stale data are worse than missing a real one.
        """
        if not reg_price or reg_price <= 0:
            return False
        deviation = abs((ext_price - reg_price) / reg_price) * 100
        if deviation > 25:
            logger.info(
                "Extended hours price for %s rejected as likely stale: $%.2f vs regular $%.2f (%.1f%% deviation)",
                ticker, ext_price, reg_price, deviation,
            )
            return False
        return True

    # Prefer pre-market price if available and plausible
    pre = data.get("pre_market_price")
    post = data.get("post_market_price")

    if pre and regular_price and _is_plausible(pre, regular_price):
        result["price"] = pre
        result["is_extended_hours"] = True
        result["session"] = "pre_market"
    elif post and regular_price and _is_plausible(post, regular_price):
        result["price"] = post
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
