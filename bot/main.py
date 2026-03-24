"""
Telegram bot entry point.

Uses python-telegram-bot v20+ (async).
Registers all command handlers and starts the bot with APScheduler for jobs.
"""

from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

import config
from bot.handlers import (
    start, status, portfolio, brief, candidate, score, plan,
    concentration, ack, reflect, trade, sync, export, checkpoint,
)

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify the user via Telegram."""
    logger.error("Exception while handling update %s:", update, exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ An error occurred: {context.error}",
            )
        except Exception:
            logger.exception("Failed to send error notification")


def setup_scheduled_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all scheduled jobs with APScheduler."""
    from jobs import morning_brief, catalyst_alerts, price_check, keepalive, false_negative_tracker, weekly_audit, canary_check, profit_defense, weekly_triage

    # Morning brief: 8:00 AM SGT (0:00 UTC) weekdays
    scheduler.add_job(
        morning_brief.run,
        CronTrigger(hour=0, minute=0, day_of_week="mon-fri"),  # UTC = SGT-8
        id="morning_brief",
        name="Morning Brief",
        replace_existing=True,
    )

    # Catalyst countdown alerts: 9:00 PM SGT (13:00 UTC) daily
    scheduler.add_job(
        catalyst_alerts.run,
        CronTrigger(hour=13, minute=0),  # UTC
        id="catalyst_alerts",
        name="Catalyst Alerts",
        replace_existing=True,
    )

    # Price movement detection: every 10 min during US market hours
    # US market = 9:30 AM - 4:00 PM ET = ~9:30 PM - 4:00 AM SGT
    scheduler.add_job(
        price_check.run,
        CronTrigger(minute="*/10", hour="13-23,0-4", day_of_week="mon-fri"),  # UTC approximation
        id="price_check",
        name="Price Check",
        replace_existing=True,
    )

    # Keepalive: every 12 hours
    scheduler.add_job(
        keepalive.run,
        CronTrigger(hour="*/12"),
        id="keepalive",
        name="Supabase Keepalive",
        replace_existing=True,
    )

    # False negative tracker: 10:30 PM SGT (14:30 UTC) weekdays
    scheduler.add_job(
        false_negative_tracker.run,
        CronTrigger(hour=14, minute=30, day_of_week="mon-fri"),
        id="false_negative_tracker",
        name="False Negative Tracker",
        replace_existing=True,
    )

    # Weekly audit: Sunday 10:00 PM SGT (14:00 UTC)
    scheduler.add_job(
        weekly_audit.run,
        CronTrigger(hour=14, minute=0, day_of_week="sun"),
        id="weekly_audit",
        name="Weekly Audit Snapshot",
        replace_existing=True,
    )

    # Canary health check: every 6 hours
    scheduler.add_job(
        canary_check.run,
        CronTrigger(hour="*/6"),
        id="canary_check",
        name="Canary Health Check",
        replace_existing=True,
    )

    # Profit defense: every hour during US market hours
    scheduler.add_job(
        profit_defense.run,
        CronTrigger(minute=30, hour="13-23,0-4", day_of_week="mon-fri"),  # UTC
        id="profit_defense",
        name="Profit Defense Check",
        replace_existing=True,
    )

    # Weekly triage: Sunday 10:00 PM SGT (14:00 UTC)
    scheduler.add_job(
        weekly_triage.run,
        CronTrigger(hour=14, minute=0, day_of_week="sun"),
        id="weekly_triage",
        name="Weekly Position Triage",
        replace_existing=True,
    )


async def post_init(application) -> None:
    """Called after the Application is initialized and the event loop is running."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    setup_scheduled_jobs(scheduler)
    scheduler.start()
    logger.info("Scheduled jobs started")


def main() -> None:
    """Start the bot."""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Exiting.")
        sys.exit(1)

    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start.handle))
    app.add_handler(CommandHandler("status", status.handle))
    app.add_handler(CommandHandler("portfolio", portfolio.handle))
    app.add_handler(CommandHandler("brief", brief.handle))
    app.add_handler(CommandHandler("candidate", candidate.handle))
    app.add_handler(CommandHandler("score", score.handle))
    app.add_handler(CommandHandler("plan", plan.handle))
    app.add_handler(CommandHandler("concentration", concentration.handle))
    app.add_handler(CommandHandler("ack", ack.handle))
    app.add_handler(CommandHandler("reflect", reflect.handle))
    app.add_handler(CommandHandler("trade", trade.handle))
    app.add_handler(CommandHandler("export", export.handle))
    app.add_handler(CommandHandler("checkpoint", checkpoint.handle))

    # Document handler for CSV sync
    app.add_handler(MessageHandler(filters.Document.ALL, sync.handle_document))

    # Error handler
    app.add_error_handler(error_handler)

    logger.info("Strategy 5.x bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
