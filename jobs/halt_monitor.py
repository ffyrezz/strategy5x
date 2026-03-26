"""
Scheduled job: Monitor NASDAQ trading halts for pipeline tickers.

Runs every 2 minutes during US market hours.
Checks the NASDAQ Trading Halt RSS feed for any halts on tickers
in the pipeline (positions + candidates + watchlist).

Trading halts on biotech stocks often precede binary catalysts
(PDUFA results, Phase 3 data releases). Detecting a halt early
gives the user critical seconds/minutes to prepare for the news.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

import db
from utils.telegram_sender import send_message as send_telegram
from utils.timezone import now_utc

logger = logging.getLogger(__name__)

HALT_FEED_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"

# Halt reason codes from NASDAQ
HALT_REASONS = {
    "T1": "News Pending",
    "T2": "News Dissemination",
    "T5": "Single Stock Trading Pause (10% move in 5 min)",
    "T6": "Extraordinary Market Activity",
    "T8": "Exchange-Traded Product Halt",
    "T12": "IPO Halt",
    "H4": "Non-compliance",
    "H9": "SEC Suspension",
    "H10": "SEC Trading Suspension Release",
    "H11": "Additional Information Requested",
    "LUDP": "Limit Up-Limit Down Pause",
    "LUDS": "Limit Up-Limit Down Straddle Condition",
    "M": "Volatility Trading Pause",
    "M1": "Market-Wide Circuit Breaker Level 1",
    "M2": "Market-Wide Circuit Breaker Level 2",
    "M3": "Market-Wide Circuit Breaker Level 3",
}

# Track which halts we've already alerted on (prevent spam)
_alerted_halts: set[str] = set()


def _parse_halt_feed() -> list[dict]:
    """Fetch and parse the NASDAQ trading halt RSS feed."""
    try:
        r = httpx.get(HALT_FEED_URL, follow_redirects=True, timeout=15)
        r.raise_for_status()
        
        root = ET.fromstring(r.text)
        ns = {"ndaq": "http://www.nasdaqtrader.com/"}
        
        halts = []
        for item in root.findall(".//item"):
            title = item.find("title")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            
            if title is None:
                continue
            
            ticker = title.text.strip() if title.text else ""
            description = desc.text.strip() if desc is not None and desc.text else ""
            date_str = pub_date.text.strip() if pub_date is not None and pub_date.text else ""
            
            # Parse NASDAQ halt fields from description
            # Format: "Reason: T1 | Market: NASDAQ | Date: 2026-03-25 | ..."
            halt_info = {
                "ticker": ticker,
                "description": description,
                "pub_date": date_str,
                "reason_code": "",
                "reason_text": "",
                "halt_date": "",
                "halt_time": "",
                "resumption_date": "",
                "resumption_time": "",
                "market": "",
            }
            
            # Parse ndaq: namespaced fields
            for field in ["HaltDate", "HaltTime", "ResumptionDate", "ResumptionTime",
                         "ReasonCode", "Market"]:
                el = item.find(f"ndaq:{field}", ns)
                if el is not None and el.text:
                    key = field[0].lower() + field[1:]
                    # Convert camelCase to snake_case
                    snake = ""
                    for c in key:
                        if c.isupper():
                            snake += "_" + c.lower()
                        else:
                            snake += c
                    halt_info[snake] = el.text.strip()
            
            reason_code = halt_info.get("reason_code", "")
            halt_info["reason_text"] = HALT_REASONS.get(reason_code, reason_code)
            
            halts.append(halt_info)
        
        return halts
    
    except Exception as exc:
        logger.warning("Failed to fetch NASDAQ halt feed: %s", exc)
        return []


async def run() -> None:
    """Check for trading halts on pipeline tickers."""
    logger.info("Halt monitor starting")
    
    try:
        # Get all tickers we care about
        positions = db.get_active_positions()
        position_tickers = {p["ticker"] for p in positions}
        
        # Get pipeline candidates (non-rejected)
        try:
            resp = (
                db.get_client()
                .table("pipeline_candidates")
                .select("ticker,status")
                .not_.in_("status", ["eliminated", "expired"])
                .execute()
            )
            pipeline_tickers = {c["ticker"] for c in (resp.data or [])}
        except Exception:
            pipeline_tickers = set()
        
        watched_tickers = position_tickers | pipeline_tickers
        if not watched_tickers:
            return
        
        # Fetch halt data
        halts = _parse_halt_feed()
        if not halts:
            return
        
        # Check for matches
        for halt in halts:
            ticker = halt["ticker"]
            if ticker not in watched_tickers:
                continue
            
            # Build dedupe key
            halt_date = halt.get("halt_date", "")
            halt_time = halt.get("halt_time", "")
            dedupe_key = f"halt_{ticker}_{halt_date}_{halt_time}"
            
            if dedupe_key in _alerted_halts:
                continue
            _alerted_halts.add(dedupe_key)
            
            # Determine if this is a resumption or a new halt
            resumption = halt.get("resumption_date", "")
            is_resumed = bool(resumption)
            
            reason = halt.get("reason_text", halt.get("reason_code", "unknown"))
            is_position = ticker in position_tickers
            
            # Build alert message
            if is_resumed:
                msg = (
                    f"TRADING RESUMED: {ticker}\n"
                    f"Resumed at: {resumption} {halt.get('resumption_time', '')}\n"
                    f"Was halted: {reason}\n"
                    f"{'Position: ' + str(next((p['quantity'] for p in positions if p['ticker'] == ticker), '?')) + ' shares' if is_position else 'Pipeline ticker'}\n"
                    f"Check news immediately for catalyst result."
                )
            else:
                urgency = "POSITION HALTED" if is_position else "PIPELINE HALT"
                msg = (
                    f"{urgency}: {ticker}\n"
                    f"Halted at: {halt_date} {halt_time}\n"
                    f"Reason: {reason}\n"
                    f"{'Position: ' + str(next((p['quantity'] for p in positions if p['ticker'] == ticker), '?')) + ' shares @ $' + str(next((p['avg_cost'] for p in positions if p['ticker'] == ticker), '?')) if is_position else 'Pipeline ticker — not currently holding'}\n"
                    f"Action: Check news sources. Prepare pre-commitment plan execution.\n"
                    f"{'Review your /plan for ' + ticker if is_position else 'No position — observe only'}"
                )
            
            # Send Telegram alert
            await send_telegram(msg)
            
            # Log to decision audit trail
            db.log_decision(
                event_type="catalyst_alert",
                ticker=ticker,
                source="price_check",
                advice_summary=f"Trading {'resumed' if is_resumed else 'halted'}: {ticker}. Reason: {reason}",
                advice_action="no_action",
                user_response="pending",
            )
            
            # Insert alert record
            try:
                db.insert_alert({
                    "alert_type": "trading_halt",
                    "priority": "critical" if is_position else "high",
                    "ticker": ticker,
                    "title": f"{'RESUMED' if is_resumed else 'HALTED'}: {ticker} — {reason}",
                    "body": msg,
                    "action_required": is_position,
                    "channel": "telegram",
                    "delivery_status": "sent",
                    "delivery_attempts": 1,
                    "dedupe_key": dedupe_key,
                    "sent_at": now_utc().isoformat(),
                    "created_at": now_utc().isoformat(),
                })
            except Exception:
                pass  # Deduped
            
            logger.info("Halt alert sent: %s (%s)", ticker, reason)
    
    except Exception as exc:
        logger.error("Halt monitor failed: %s", exc, exc_info=True)
        db.log_error_alert("halt_monitor", str(exc))


def main():
    """Entry point for testing: python -m jobs.halt_monitor"""
    import asyncio
    asyncio.run(run())


if __name__ == "__main__":
    main()
