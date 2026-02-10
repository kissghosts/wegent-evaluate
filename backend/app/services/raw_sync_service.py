"""
Service for synchronizing data from Raw DB (task_manager database).
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.raw_database import get_raw_session_factory, is_raw_db_configured
from app.models import (
    DailyStats,
    HourlyStats,
    InjectionMode,
    KbDailyStats,
    RagRecordRef,
    SyncCheckpoint,
)

logger = structlog.get_logger(__name__)


def get_rag_mode(context_type: str, type_data: Dict[str, Any]) -> str:
    """Determine RAG mode from context type and type_data.

    Args:
        context_type: 'knowledge_base' or 'selected_documents'
        type_data: JSON data containing rag_result

    Returns:
        One of: 'rag_retrieval', 'direct_injection', 'selected_documents', 'unknown'
    """
    if context_type == "selected_documents":
        return InjectionMode.SELECTED_DOCUMENTS.value

    rag_result = type_data.get("rag_result", {}) if type_data else {}
    injection_mode = rag_result.get("injection_mode", "")

    if injection_mode == "rag_retrieval":
        return InjectionMode.RAG_RETRIEVAL.value
    elif injection_mode == "direct_injection":
        return InjectionMode.DIRECT_INJECTION.value
    else:
        return InjectionMode.UNKNOWN.value


def get_knowledge_id(context_type: str, type_data: Dict[str, Any]) -> Optional[int]:
    """Extract knowledge_id from type_data.

    Args:
        context_type: 'knowledge_base' or 'selected_documents'
        type_data: JSON data

    Returns:
        Knowledge base ID or None
    """
    if not type_data:
        return None

    if context_type == "selected_documents":
        return type_data.get("knowledge_base_id")
    else:
        return type_data.get("knowledge_id")


class RawSyncService:
    """Service for synchronizing data from Raw DB."""

    def __init__(self, db: AsyncSession):
        """Initialize with local database session.

        Args:
            db: Local database session (wegent_evaluate)
        """
        self.db = db

    async def get_checkpoint(self, sync_type: str) -> Optional[SyncCheckpoint]:
        """Get sync checkpoint for given type.

        Args:
            sync_type: 'hourly' or 'daily'

        Returns:
            SyncCheckpoint or None
        """
        result = await self.db.execute(
            select(SyncCheckpoint).where(SyncCheckpoint.sync_type == sync_type)
        )
        return result.scalar_one_or_none()

    async def update_checkpoint(
        self,
        sync_type: str,
        last_raw_id: int,
        status: str,
        records_synced: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update or create sync checkpoint.

        Args:
            sync_type: 'hourly' or 'daily'
            last_raw_id: Last synced raw ID
            status: 'success' or 'failed'
            records_synced: Number of records synced
            error_message: Error message if failed
        """
        checkpoint = await self.get_checkpoint(sync_type)

        if checkpoint:
            checkpoint.last_raw_id = last_raw_id
            checkpoint.last_sync_time = datetime.utcnow()
            checkpoint.status = status
            checkpoint.records_synced = records_synced
            checkpoint.error_message = error_message
        else:
            checkpoint = SyncCheckpoint(
                sync_type=sync_type,
                last_raw_id=last_raw_id,
                last_sync_time=datetime.utcnow(),
                status=status,
                records_synced=records_synced,
                error_message=error_message,
            )
            self.db.add(checkpoint)

        await self.db.commit()

    async def fetch_incremental_records(
        self, last_raw_id: int, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch incremental records from Raw DB.

        Args:
            last_raw_id: Last synced raw ID
            limit: Maximum records to fetch

        Returns:
            List of records from subtask_contexts
        """
        if not is_raw_db_configured():
            logger.warning("Raw DB not configured, skipping fetch")
            return []

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return []

        async with session_factory() as raw_session:
            query = text("""
                SELECT
                    id,
                    subtask_id,
                    user_id,
                    context_type,
                    name,
                    status,
                    type_data,
                    created_at
                FROM subtask_contexts
                WHERE id > :last_id
                  AND context_type IN ('knowledge_base', 'selected_documents')
                  AND subtask_id > 0
                ORDER BY id ASC
                LIMIT :limit
            """)

            result = await raw_session.execute(
                query, {"last_id": last_raw_id, "limit": limit}
            )

            records = []
            for row in result.fetchall():
                # Parse type_data JSON
                import json
                type_data = row.type_data
                if isinstance(type_data, str):
                    type_data = json.loads(type_data)

                records.append({
                    "id": row.id,
                    "subtask_id": row.subtask_id,
                    "user_id": row.user_id,
                    "context_type": row.context_type,
                    "name": row.name,
                    "status": row.status,
                    "type_data": type_data,
                    "created_at": row.created_at,
                })

            return records

    async def sync_records(self, records: List[Dict[str, Any]]) -> Tuple[int, int]:
        """Sync records to local database.

        Args:
            records: List of records from Raw DB

        Returns:
            (inserted_count, skipped_count)
        """
        inserted = 0
        skipped = 0

        for record in records:
            # Check if already exists
            existing = await self.db.execute(
                select(RagRecordRef).where(RagRecordRef.raw_id == record["id"])
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            # Determine mode and knowledge_id
            rag_mode = get_rag_mode(record["context_type"], record["type_data"])
            kb_id = get_knowledge_id(record["context_type"], record["type_data"])

            # Create reference record
            ref = RagRecordRef(
                raw_id=record["id"],
                knowledge_id=kb_id,
                context_type=record["context_type"],
                injection_mode=rag_mode if rag_mode != InjectionMode.UNKNOWN.value else None,
                record_date=record["created_at"].date() if record["created_at"] else None,
            )
            self.db.add(ref)
            inserted += 1

        await self.db.commit()
        return inserted, skipped

    async def update_hourly_stats(
        self, target_date: date, hour: int, records: List[Dict[str, Any]]
    ) -> None:
        """Update hourly statistics.

        Args:
            target_date: Date for statistics
            hour: Hour (0-23)
            records: Records to count
        """
        # Count by mode
        counts = {
            InjectionMode.RAG_RETRIEVAL.value: 0,
            InjectionMode.DIRECT_INJECTION.value: 0,
            InjectionMode.SELECTED_DOCUMENTS.value: 0,
        }

        for record in records:
            mode = get_rag_mode(record["context_type"], record["type_data"])
            if mode in counts:
                counts[mode] += 1

        total = sum(counts.values())

        # Upsert hourly stats
        stmt = insert(HourlyStats).values(
            date=target_date,
            hour=hour,
            total_queries=total,
            rag_retrieval_count=counts[InjectionMode.RAG_RETRIEVAL.value],
            direct_injection_count=counts[InjectionMode.DIRECT_INJECTION.value],
            selected_documents_count=counts[InjectionMode.SELECTED_DOCUMENTS.value],
        )

        stmt = stmt.on_duplicate_key_update(
            total_queries=stmt.inserted.total_queries,
            rag_retrieval_count=stmt.inserted.rag_retrieval_count,
            direct_injection_count=stmt.inserted.direct_injection_count,
            selected_documents_count=stmt.inserted.selected_documents_count,
        )

        await self.db.execute(stmt)
        await self.db.commit()

    async def update_daily_stats(
        self, target_date: date, records: List[Dict[str, Any]]
    ) -> None:
        """Update daily statistics.

        Args:
            target_date: Date for statistics
            records: Records to count
        """
        # Count by mode
        counts = {
            InjectionMode.RAG_RETRIEVAL.value: 0,
            InjectionMode.DIRECT_INJECTION.value: 0,
            InjectionMode.SELECTED_DOCUMENTS.value: 0,
        }

        # Track unique KB and users
        kb_ids = set()
        user_ids = set()

        for record in records:
            mode = get_rag_mode(record["context_type"], record["type_data"])
            if mode in counts:
                counts[mode] += 1

            kb_id = get_knowledge_id(record["context_type"], record["type_data"])
            if kb_id:
                kb_ids.add(kb_id)

            if record.get("user_id"):
                user_ids.add(record["user_id"])

        total = sum(counts.values())

        # Upsert daily stats
        stmt = insert(DailyStats).values(
            date=target_date,
            total_queries=total,
            rag_retrieval_count=counts[InjectionMode.RAG_RETRIEVAL.value],
            direct_injection_count=counts[InjectionMode.DIRECT_INJECTION.value],
            selected_documents_count=counts[InjectionMode.SELECTED_DOCUMENTS.value],
            active_kb_count=len(kb_ids),
            active_user_count=len(user_ids),
        )

        stmt = stmt.on_duplicate_key_update(
            total_queries=DailyStats.total_queries + stmt.inserted.total_queries,
            rag_retrieval_count=DailyStats.rag_retrieval_count + stmt.inserted.rag_retrieval_count,
            direct_injection_count=DailyStats.direct_injection_count + stmt.inserted.direct_injection_count,
            selected_documents_count=DailyStats.selected_documents_count + stmt.inserted.selected_documents_count,
            active_kb_count=stmt.inserted.active_kb_count,  # Will be recalculated in daily task
            active_user_count=stmt.inserted.active_user_count,  # Will be recalculated in daily task
        )

        await self.db.execute(stmt)
        await self.db.commit()

    async def update_kb_daily_stats(
        self, target_date: date, records: List[Dict[str, Any]]
    ) -> None:
        """Update knowledge base daily statistics.

        Args:
            target_date: Date for statistics
            records: Records to count
        """
        # Group by knowledge_id
        kb_stats: Dict[int, Dict[str, int]] = {}

        for record in records:
            kb_id = get_knowledge_id(record["context_type"], record["type_data"])
            if not kb_id:
                continue

            if kb_id not in kb_stats:
                kb_stats[kb_id] = {
                    InjectionMode.RAG_RETRIEVAL.value: 0,
                    InjectionMode.DIRECT_INJECTION.value: 0,
                    InjectionMode.SELECTED_DOCUMENTS.value: 0,
                }

            mode = get_rag_mode(record["context_type"], record["type_data"])
            if mode in kb_stats[kb_id]:
                kb_stats[kb_id][mode] += 1

        # Upsert each KB stats
        for kb_id, counts in kb_stats.items():
            total = sum(counts.values())

            stmt = insert(KbDailyStats).values(
                date=target_date,
                knowledge_id=kb_id,
                total_queries=total,
                rag_retrieval_count=counts[InjectionMode.RAG_RETRIEVAL.value],
                direct_injection_count=counts[InjectionMode.DIRECT_INJECTION.value],
                selected_documents_count=counts[InjectionMode.SELECTED_DOCUMENTS.value],
            )

            stmt = stmt.on_duplicate_key_update(
                total_queries=KbDailyStats.total_queries + stmt.inserted.total_queries,
                rag_retrieval_count=KbDailyStats.rag_retrieval_count + stmt.inserted.rag_retrieval_count,
                direct_injection_count=KbDailyStats.direct_injection_count + stmt.inserted.direct_injection_count,
                selected_documents_count=KbDailyStats.selected_documents_count + stmt.inserted.selected_documents_count,
            )

            await self.db.execute(stmt)

        await self.db.commit()

    async def run_hourly_sync(self) -> Dict[str, Any]:
        """Run hourly incremental sync.

        Returns:
            Sync result summary
        """
        if not is_raw_db_configured():
            return {"status": "skipped", "reason": "Raw DB not configured"}

        try:
            # Get checkpoint
            checkpoint = await self.get_checkpoint("hourly")
            last_raw_id = checkpoint.last_raw_id if checkpoint else 0

            # Fetch incremental records
            records = await self.fetch_incremental_records(last_raw_id)

            if not records:
                await self.update_checkpoint("hourly", last_raw_id, "success", 0)
                return {"status": "success", "records_synced": 0, "message": "No new records"}

            # Get max raw_id for checkpoint update
            max_raw_id = max(r["id"] for r in records)

            # Sync records to local DB
            inserted, skipped = await self.sync_records(records)

            # Group records by date and hour for stats update
            records_by_date_hour: Dict[Tuple[date, int], List[Dict]] = {}
            for record in records:
                if record["created_at"]:
                    record_date = record["created_at"].date()
                    record_hour = record["created_at"].hour
                    key = (record_date, record_hour)
                    if key not in records_by_date_hour:
                        records_by_date_hour[key] = []
                    records_by_date_hour[key].append(record)

            # Update statistics
            for (record_date, record_hour), hour_records in records_by_date_hour.items():
                await self.update_hourly_stats(record_date, record_hour, hour_records)

            # Update daily stats (grouped by date)
            records_by_date: Dict[date, List[Dict]] = {}
            for record in records:
                if record["created_at"]:
                    record_date = record["created_at"].date()
                    if record_date not in records_by_date:
                        records_by_date[record_date] = []
                    records_by_date[record_date].append(record)

            for record_date, date_records in records_by_date.items():
                await self.update_daily_stats(record_date, date_records)
                await self.update_kb_daily_stats(record_date, date_records)

            # Update checkpoint
            await self.update_checkpoint("hourly", max_raw_id, "success", inserted)

            logger.info(
                "Hourly sync completed",
                inserted=inserted,
                skipped=skipped,
                max_raw_id=max_raw_id,
            )

            return {
                "status": "success",
                "records_synced": inserted,
                "records_skipped": skipped,
                "last_raw_id": max_raw_id,
            }

        except Exception as e:
            logger.exception("Hourly sync failed", error=str(e))
            await self.update_checkpoint("hourly", last_raw_id, "failed", 0, str(e))
            return {"status": "failed", "error": str(e)}

    async def run_daily_sync(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Run daily sync to recalculate yesterday's complete statistics.

        Args:
            target_date: Date to recalculate (default: yesterday)

        Returns:
            Sync result summary
        """
        if not is_raw_db_configured():
            return {"status": "skipped", "reason": "Raw DB not configured"}

        if target_date is None:
            target_date = date.today() - timedelta(days=1)

        try:
            # Recalculate daily stats from rag_record_refs
            await self.recalculate_daily_stats(target_date)

            # Update KB names from Raw DB
            await self.refresh_kb_names(target_date)

            await self.update_checkpoint("daily", 0, "success")

            logger.info("Daily sync completed", target_date=target_date)

            return {"status": "success", "target_date": str(target_date)}

        except Exception as e:
            logger.exception("Daily sync failed", error=str(e))
            await self.update_checkpoint("daily", 0, "failed", 0, str(e))
            return {"status": "failed", "error": str(e)}

    async def recalculate_daily_stats(self, target_date: date) -> None:
        """Recalculate daily statistics from rag_record_refs.

        Args:
            target_date: Date to recalculate
        """
        # Query aggregated stats from rag_record_refs
        result = await self.db.execute(
            select(
                func.count(RagRecordRef.id).label("total"),
                func.sum(
                    func.IF(
                        RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value,
                        1,
                        0,
                    )
                ).label("rag_retrieval"),
                func.sum(
                    func.IF(
                        RagRecordRef.injection_mode == InjectionMode.DIRECT_INJECTION.value,
                        1,
                        0,
                    )
                ).label("direct_injection"),
                func.sum(
                    func.IF(
                        RagRecordRef.context_type == "selected_documents",
                        1,
                        0,
                    )
                ).label("selected_documents"),
                func.count(func.distinct(RagRecordRef.knowledge_id)).label("active_kb"),
            ).where(RagRecordRef.record_date == target_date)
        )

        row = result.fetchone()
        if not row:
            return

        # Update or insert daily stats
        stmt = insert(DailyStats).values(
            date=target_date,
            total_queries=row.total or 0,
            rag_retrieval_count=row.rag_retrieval or 0,
            direct_injection_count=row.direct_injection or 0,
            selected_documents_count=row.selected_documents or 0,
            active_kb_count=row.active_kb or 0,
        )

        stmt = stmt.on_duplicate_key_update(
            total_queries=row.total or 0,
            rag_retrieval_count=row.rag_retrieval or 0,
            direct_injection_count=row.direct_injection or 0,
            selected_documents_count=row.selected_documents or 0,
            active_kb_count=row.active_kb or 0,
        )

        await self.db.execute(stmt)
        await self.db.commit()

    async def refresh_kb_names(self, target_date: date) -> None:
        """Refresh knowledge base names from Raw DB.

        Args:
            target_date: Date for KB stats to update
        """
        if not is_raw_db_configured():
            return

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return

        # Get unique KB IDs from kb_daily_stats for the target date
        result = await self.db.execute(
            select(KbDailyStats.knowledge_id).where(
                KbDailyStats.date == target_date
            ).distinct()
        )
        kb_ids = [row[0] for row in result.fetchall()]

        if not kb_ids:
            return

        # Fetch KB names from Raw DB
        async with session_factory() as raw_session:
            # Query kinds table for KnowledgeBase entries
            query = text("""
                SELECT id, name, namespace, json
                FROM kinds
                WHERE kind = 'KnowledgeBase'
                  AND id IN :kb_ids
            """)

            result = await raw_session.execute(query, {"kb_ids": tuple(kb_ids)})

            for row in result.fetchall():
                import json as json_module
                kb_json = row.json
                if isinstance(kb_json, str):
                    kb_json = json_module.loads(kb_json)

                # Extract display name from JSON
                display_name = kb_json.get("spec", {}).get("name", row.name)
                namespace = kb_json.get("metadata", {}).get("namespace", row.namespace)

                # Update kb_daily_stats
                await self.db.execute(
                    KbDailyStats.__table__.update()
                    .where(
                        KbDailyStats.date == target_date,
                        KbDailyStats.knowledge_id == row.id,
                    )
                    .values(knowledge_name=display_name, namespace=namespace)
                )

        await self.db.commit()

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status.

        Returns:
            Status information for both hourly and daily sync
        """
        hourly = await self.get_checkpoint("hourly")
        daily = await self.get_checkpoint("daily")

        return {
            "raw_db_configured": is_raw_db_configured(),
            "hourly": {
                "last_sync_time": hourly.last_sync_time.isoformat() if hourly and hourly.last_sync_time else None,
                "last_raw_id": hourly.last_raw_id if hourly else 0,
                "status": hourly.status if hourly else None,
                "records_synced": hourly.records_synced if hourly else 0,
                "error_message": hourly.error_message if hourly else None,
            } if hourly else None,
            "daily": {
                "last_sync_time": daily.last_sync_time.isoformat() if daily and daily.last_sync_time else None,
                "status": daily.status if daily else None,
                "error_message": daily.error_message if daily else None,
            } if daily else None,
        }
