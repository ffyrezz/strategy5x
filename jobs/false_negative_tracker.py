"""
Scheduled job: Track rejected candidates' price movements.

Runs daily at 10:30 PM SGT.
For each rejected candidate within the 30-day tracking window,
checks if price moved >25% above rejection price.
"""

from __future__ import annotations

import logging

import config
import db
from data.market_data import get_price_data
from utils.timezone import now_utc

logger = logging.getLogger(__name__)


async def run() -> None:
    """Check rejected candidates for false-negative signals."""
    logger.info("False negative tracker starting")

    try:
        candidates = db.get_rejected_candidates_for_tracking()
        if not candidates:
            logger.info("No rejected candidates to track")
            return

        flagged = 0
        for cand in candidates:
            ticker = cand["ticker"]
            rejection_price = cand.get("false_negative_price_at_rejection")

            if not rejection_price:
                continue

            rejection_price = float(rejection_price)

            try:
                price_data = get_price_data(ticker)
                current = price_data.get("price")

                if not current:
                    continue

                move_pct = ((current - rejection_price) / rejection_price) * 100

                # Update peak price tracking
                peak = float(cand.get("false_negative_peak_price") or 0)
                if current > peak:
                    db.update_candidate(cand["id"], {
                        "false_negative_peak_price": current,
                        "updated_at": now_utc().isoformat(),
                    })

                # Check threshold
                if move_pct >= config.FALSE_NEGATIVE_THRESHOLD_PCT and not cand.get("false_negative_flag"):
                    db.update_candidate(cand["id"], {
                        "false_negative_flag": True,
                        "false_negative_peak_price": max(current, peak),
                        "updated_at": now_utc().isoformat(),
                    })
                    flagged += 1
                    logger.info(
                        "False negative flagged: %s moved +%.1f%% since rejection (was $%.2f, now $%.2f)",
                        ticker, move_pct, rejection_price, current,
                    )

            except Exception as exc:
                logger.warning("FN tracking failed for %s: %s", ticker, exc)

        if flagged:
            logger.info("False negative tracker: %d new flags", flagged)

    except Exception as exc:
        logger.error("False negative tracker failed: %s", exc, exc_info=True)
        db.log_error_alert("false_negative_tracker", str(exc))
