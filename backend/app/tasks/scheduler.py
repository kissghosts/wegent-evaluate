"""
APScheduler configuration.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Set up scheduled tasks."""
    from app.tasks.evaluation_task import run_daily_evaluation
    from app.tasks.sync_task import run_daily_sync
    from app.tasks.raw_sync_task import run_hourly_raw_sync, run_daily_raw_sync

    # Parse cron expressions
    sync_trigger = CronTrigger.from_crontab(settings.SYNC_CRON_EXPRESSION)
    evaluation_trigger = CronTrigger.from_crontab(settings.EVALUATION_CRON_EXPRESSION)
    raw_sync_hourly_trigger = CronTrigger.from_crontab(settings.RAW_SYNC_HOURLY_CRON)
    raw_sync_daily_trigger = CronTrigger.from_crontab(settings.RAW_SYNC_DAILY_CRON)

    # Add jobs
    scheduler.add_job(
        run_daily_sync,
        trigger=sync_trigger,
        id="daily_sync",
        name="Daily Data Sync",
        replace_existing=True,
    )

    scheduler.add_job(
        run_daily_evaluation,
        trigger=evaluation_trigger,
        id="daily_evaluation",
        name="Daily Evaluation",
        replace_existing=True,
    )

    # Raw DB sync tasks
    scheduler.add_job(
        run_hourly_raw_sync,
        trigger=raw_sync_hourly_trigger,
        id="hourly_raw_sync",
        name="Hourly Raw Data Sync",
        replace_existing=True,
    )

    scheduler.add_job(
        run_daily_raw_sync,
        trigger=raw_sync_daily_trigger,
        id="daily_raw_sync",
        name="Daily Raw Data Sync",
        replace_existing=True,
    )


def start_scheduler():
    """Start the scheduler."""
    setup_scheduler()
    scheduler.start()


def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown()
