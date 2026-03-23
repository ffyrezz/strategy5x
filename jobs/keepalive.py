"""
Scheduled job: Supabase keepalive ping.

Runs every 12 hours to prevent free-tier auto-pause (7-day inactivity).
"""

from __future__ import annotations

import logging

import db

logger = logging.getLogger(__name__)


async def run() -> None:
    """Ping Supabase to keep it alive."""
    logger.info("Keepalive ping starting")

    success = db.keepalive_ping()

    if success:
        logger.info("Keepalive ping: OK")
    else:
        logger.error("Keepalive ping: FAILED")
        db.log_error_alert("keepalive", "Supabase keepalive ping failed")
