"""
Raw data sync scheduled tasks.
"""
import structlog

from app.core.database import AsyncSessionLocal
from app.core.raw_database import is_raw_db_configured
from app.services.raw_sync_service import RawSyncService

logger = structlog.get_logger(__name__)


async def run_hourly_raw_sync():
    """Run hourly raw data sync task."""
    if not is_raw_db_configured():
        logger.info("Raw DB not configured, skipping hourly sync")
        return

    logger.info("Starting hourly raw data sync")

    async with AsyncSessionLocal() as db:
        service = RawSyncService(db)
        result = await service.run_hourly_sync()

        if result.get("status") == "success":
            logger.info(
                "Hourly raw sync completed",
                records_synced=result.get("records_synced", 0),
            )
        else:
            logger.error(
                "Hourly raw sync failed",
                error=result.get("error"),
            )


async def run_daily_raw_sync():
    """Run daily raw data sync task."""
    if not is_raw_db_configured():
        logger.info("Raw DB not configured, skipping daily sync")
        return

    logger.info("Starting daily raw data sync")

    async with AsyncSessionLocal() as db:
        service = RawSyncService(db)
        result = await service.run_daily_sync()

        if result.get("status") == "success":
            logger.info(
                "Daily raw sync completed",
                target_date=result.get("target_date"),
            )
        else:
            logger.error(
                "Daily raw sync failed",
                error=result.get("error"),
            )
