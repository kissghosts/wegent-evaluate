"""
Service for daily report statistics and analytics.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.raw_database import get_raw_session_factory, is_raw_db_configured
from app.models import (
    DailyStats,
    HourlyStats,
    InjectionMode,
    KbDailyStats,
    RagRecordRef,
)

logger = structlog.get_logger(__name__)


class DailyReportService:
    """Service for daily report queries and analytics."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Local database session
        """
        self.db = db

    async def get_daily_overview(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get daily overview statistics.

        Args:
            start_date: Start date (default: 7 days ago)
            end_date: End date (default: today)

        Returns:
            Overview with summary and daily breakdown
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=6)

        # Query daily stats
        result = await self.db.execute(
            select(DailyStats)
            .where(DailyStats.date >= start_date, DailyStats.date <= end_date)
            .order_by(DailyStats.date.desc())
        )
        daily_stats = result.scalars().all()

        # Calculate summary
        summary = {
            "total_queries": sum(d.total_queries for d in daily_stats),
            "rag_retrieval_count": sum(d.rag_retrieval_count for d in daily_stats),
            "direct_injection_count": sum(d.direct_injection_count for d in daily_stats),
            "selected_documents_count": sum(d.selected_documents_count for d in daily_stats),
            "active_kb_count": max((d.active_kb_count for d in daily_stats), default=0),
            "active_user_count": max((d.active_user_count for d in daily_stats), default=0),
        }

        # Get today's stats and yesterday's for comparison
        today_stats = next((d for d in daily_stats if d.date == date.today()), None)
        yesterday_stats = next(
            (d for d in daily_stats if d.date == date.today() - timedelta(days=1)), None
        )

        comparison = None
        if today_stats and yesterday_stats and yesterday_stats.total_queries > 0:
            comparison = {
                "total_queries_change": (
                    (today_stats.total_queries - yesterday_stats.total_queries)
                    / yesterday_stats.total_queries
                    * 100
                ),
                "rag_retrieval_change": (
                    (today_stats.rag_retrieval_count - yesterday_stats.rag_retrieval_count)
                    / max(yesterday_stats.rag_retrieval_count, 1)
                    * 100
                ),
            }

        return {
            "summary": summary,
            "comparison": comparison,
            "daily": [
                {
                    "date": d.date.isoformat(),
                    "total_queries": d.total_queries,
                    "rag_retrieval_count": d.rag_retrieval_count,
                    "direct_injection_count": d.direct_injection_count,
                    "selected_documents_count": d.selected_documents_count,
                    "active_kb_count": d.active_kb_count,
                    "active_user_count": d.active_user_count,
                }
                for d in daily_stats
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

    async def get_trends(
        self,
        days: int = 7,
        granularity: str = "day",
    ) -> Dict[str, Any]:
        """Get trend data over time.

        Args:
            days: Number of days to include
            granularity: 'day' or 'hour'

        Returns:
            Trend data with time series
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        if granularity == "hour":
            # Return hourly data for the date range
            result = await self.db.execute(
                select(HourlyStats)
                .where(HourlyStats.date >= start_date, HourlyStats.date <= end_date)
                .order_by(HourlyStats.date.asc(), HourlyStats.hour.asc())
            )
            hourly_stats = result.scalars().all()

            return {
                "granularity": "hour",
                "data": [
                    {
                        "datetime": f"{h.date.isoformat()}T{h.hour:02d}:00:00",
                        "date": h.date.isoformat(),
                        "hour": h.hour,
                        "total_queries": h.total_queries,
                        "rag_retrieval_count": h.rag_retrieval_count,
                        "direct_injection_count": h.direct_injection_count,
                        "selected_documents_count": h.selected_documents_count,
                    }
                    for h in hourly_stats
                ],
            }
        else:
            # Return daily data
            result = await self.db.execute(
                select(DailyStats)
                .where(DailyStats.date >= start_date, DailyStats.date <= end_date)
                .order_by(DailyStats.date.asc())
            )
            daily_stats = result.scalars().all()

            return {
                "granularity": "day",
                "data": [
                    {
                        "date": d.date.isoformat(),
                        "total_queries": d.total_queries,
                        "rag_retrieval_count": d.rag_retrieval_count,
                        "direct_injection_count": d.direct_injection_count,
                        "selected_documents_count": d.selected_documents_count,
                        "active_kb_count": d.active_kb_count,
                    }
                    for d in daily_stats
                ],
            }

    async def get_hourly_stats(self, target_date: date) -> List[Dict[str, Any]]:
        """Get hourly statistics for a specific date.

        Args:
            target_date: Date to query

        Returns:
            List of hourly stats (24 hours)
        """
        result = await self.db.execute(
            select(HourlyStats)
            .where(HourlyStats.date == target_date)
            .order_by(HourlyStats.hour.asc())
        )
        hourly_stats = result.scalars().all()

        # Fill in missing hours with zeros
        stats_by_hour = {h.hour: h for h in hourly_stats}
        hourly_data = []

        for hour in range(24):
            if hour in stats_by_hour:
                h = stats_by_hour[hour]
                hourly_data.append({
                    "hour": hour,
                    "total_queries": h.total_queries,
                    "rag_retrieval_count": h.rag_retrieval_count,
                    "direct_injection_count": h.direct_injection_count,
                    "selected_documents_count": h.selected_documents_count,
                })
            else:
                hourly_data.append({
                    "hour": hour,
                    "total_queries": 0,
                    "rag_retrieval_count": 0,
                    "direct_injection_count": 0,
                    "selected_documents_count": 0,
                })

        return hourly_data

    async def get_top_knowledge_bases(
        self,
        target_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top knowledge bases by query count.

        Args:
            target_date: Date to query (default: today)
            limit: Number of results

        Returns:
            List of top knowledge bases
        """
        if target_date is None:
            target_date = date.today()

        result = await self.db.execute(
            select(KbDailyStats)
            .where(KbDailyStats.date == target_date)
            .order_by(KbDailyStats.total_queries.desc())
            .limit(limit)
        )
        kb_stats = result.scalars().all()

        return [
            {
                "rank": idx + 1,
                "knowledge_id": kb.knowledge_id,
                "knowledge_name": kb.knowledge_name,
                "namespace": kb.namespace,
                "total_queries": kb.total_queries,
                "rag_retrieval_count": kb.rag_retrieval_count,
                "direct_injection_count": kb.direct_injection_count,
                "selected_documents_count": kb.selected_documents_count,
                "primary_mode": self._get_primary_mode(kb),
            }
            for idx, kb in enumerate(kb_stats)
        ]

    def _get_primary_mode(self, kb: KbDailyStats) -> str:
        """Determine primary usage mode for a knowledge base."""
        modes = {
            "rag_retrieval": kb.rag_retrieval_count,
            "direct_injection": kb.direct_injection_count,
            "selected_documents": kb.selected_documents_count,
        }
        return max(modes, key=modes.get)

    async def get_knowledge_base_list(
        self,
        target_date: Optional[date] = None,
        sort_by: str = "queries",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated list of knowledge bases.

        Args:
            target_date: Date for stats (default: today)
            sort_by: Sort field ('queries' or 'name')
            limit: Page size
            offset: Offset

        Returns:
            (list of knowledge bases, total count)
        """
        if target_date is None:
            target_date = date.today()

        # Count total
        count_result = await self.db.execute(
            select(func.count(KbDailyStats.id)).where(KbDailyStats.date == target_date)
        )
        total = count_result.scalar() or 0

        # Query with sorting
        query = select(KbDailyStats).where(KbDailyStats.date == target_date)

        if sort_by == "name":
            query = query.order_by(KbDailyStats.knowledge_name.asc())
        else:
            query = query.order_by(KbDailyStats.total_queries.desc())

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        kb_stats = result.scalars().all()

        return [
            {
                "knowledge_id": kb.knowledge_id,
                "knowledge_name": kb.knowledge_name,
                "namespace": kb.namespace,
                "total_queries": kb.total_queries,
                "rag_retrieval_count": kb.rag_retrieval_count,
                "direct_injection_count": kb.direct_injection_count,
                "selected_documents_count": kb.selected_documents_count,
            }
            for kb in kb_stats
        ], total

    async def get_knowledge_base_stats(
        self,
        kb_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get statistics for a specific knowledge base.

        Args:
            kb_id: Knowledge base ID
            days: Number of days

        Returns:
            Knowledge base statistics with trends
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        # Query daily stats for this KB
        result = await self.db.execute(
            select(KbDailyStats)
            .where(
                KbDailyStats.knowledge_id == kb_id,
                KbDailyStats.date >= start_date,
                KbDailyStats.date <= end_date,
            )
            .order_by(KbDailyStats.date.asc())
        )
        kb_stats = result.scalars().all()

        # Get latest KB info
        latest = kb_stats[-1] if kb_stats else None

        # Calculate totals
        summary = {
            "knowledge_id": kb_id,
            "knowledge_name": latest.knowledge_name if latest else None,
            "namespace": latest.namespace if latest else None,
            "total_queries": sum(kb.total_queries for kb in kb_stats),
            "rag_retrieval_count": sum(kb.rag_retrieval_count for kb in kb_stats),
            "direct_injection_count": sum(kb.direct_injection_count for kb in kb_stats),
            "selected_documents_count": sum(kb.selected_documents_count for kb in kb_stats),
        }

        return {
            "summary": summary,
            "daily": [
                {
                    "date": kb.date.isoformat(),
                    "total_queries": kb.total_queries,
                    "rag_retrieval_count": kb.rag_retrieval_count,
                    "direct_injection_count": kb.direct_injection_count,
                    "selected_documents_count": kb.selected_documents_count,
                }
                for kb in kb_stats
            ],
        }

    async def get_knowledge_base_detail(self, kb_id: int) -> Optional[Dict[str, Any]]:
        """Get knowledge base detail from Raw DB.

        Args:
            kb_id: Knowledge base ID

        Returns:
            Knowledge base detail or None
        """
        if not is_raw_db_configured():
            return None

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return None

        async with session_factory() as raw_session:
            query = text("""
                SELECT id, user_id, name, namespace, json, is_active, created_at, updated_at
                FROM kinds
                WHERE kind = 'KnowledgeBase' AND id = :kb_id
            """)

            result = await raw_session.execute(query, {"kb_id": kb_id})
            row = result.fetchone()

            if not row:
                return None

            import json
            kb_json = row.json
            if isinstance(kb_json, str):
                kb_json = json.loads(kb_json)

            spec = kb_json.get("spec", {})
            retrieval_config = spec.get("retrievalConfig", {})

            return {
                "id": row.id,
                "name": spec.get("name", row.name),
                "namespace": row.namespace,
                "kb_type": spec.get("kbType"),
                "is_active": row.is_active,
                "retrieval_config": {
                    "retriever_name": retrieval_config.get("retriever_name"),
                    "retrieval_mode": retrieval_config.get("retrieval_mode"),
                    "top_k": retrieval_config.get("top_k"),
                    "score_threshold": retrieval_config.get("score_threshold"),
                    "embedding_model": retrieval_config.get("embedding_config", {}).get("model_name"),
                },
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }

    async def get_knowledge_base_queries(
        self,
        kb_id: int,
        limit: int = 20,
        offset: int = 0,
        injection_mode: Optional[str] = None,
        evaluation_status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get recent queries for a knowledge base.

        Args:
            kb_id: Knowledge base ID
            limit: Page size
            offset: Offset
            injection_mode: Filter by injection mode
            evaluation_status: Filter by evaluation status

        Returns:
            (list of queries, total count)
        """
        # Build filter conditions
        conditions = [RagRecordRef.knowledge_id == kb_id]
        if injection_mode:
            conditions.append(RagRecordRef.injection_mode == injection_mode)
        if evaluation_status:
            conditions.append(RagRecordRef.evaluation_status == evaluation_status)

        # Count total
        count_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        # Query refs
        result = await self.db.execute(
            select(RagRecordRef)
            .where(and_(*conditions))
            .order_by(RagRecordRef.record_date.desc(), RagRecordRef.id.desc())
            .offset(offset)
            .limit(limit)
        )
        refs = result.scalars().all()

        if not refs:
            return [], total

        # Fetch details from Raw DB
        raw_ids = [ref.raw_id for ref in refs]
        raw_details = await self._fetch_raw_details(raw_ids)

        # Combine data
        queries = []
        for ref in refs:
            raw_detail = raw_details.get(ref.raw_id, {})
            rag_result = raw_detail.get("type_data", {}).get("rag_result", {})

            queries.append({
                "id": ref.id,
                "raw_id": ref.raw_id,
                "record_date": ref.record_date.isoformat() if ref.record_date else None,
                "context_type": ref.context_type,
                "injection_mode": ref.injection_mode,
                "evaluation_status": ref.evaluation_status,
                "query": rag_result.get("query"),
                "chunks_count": rag_result.get("chunks_count"),
                "sources": rag_result.get("sources"),
                "created_at": raw_detail.get("created_at"),
            })

        return queries, total

    async def _fetch_raw_details(self, raw_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch raw record details from Raw DB.

        Args:
            raw_ids: List of raw IDs

        Returns:
            Dict mapping raw_id to detail
        """
        if not raw_ids or not is_raw_db_configured():
            return {}

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return {}

        async with session_factory() as raw_session:
            query = text("""
                SELECT id, context_type, name, type_data, created_at
                FROM subtask_contexts
                WHERE id IN :raw_ids
            """)

            result = await raw_session.execute(query, {"raw_ids": tuple(raw_ids)})

            details = {}
            for row in result.fetchall():
                import json
                type_data = row.type_data
                if isinstance(type_data, str):
                    type_data = json.loads(type_data)

                details[row.id] = {
                    "context_type": row.context_type,
                    "name": row.name,
                    "type_data": type_data,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }

            return details

    async def get_rag_record_detail(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed RAG record by local ID.

        Args:
            record_id: Local rag_record_refs ID

        Returns:
            Full record detail or None
        """
        # Get local ref
        result = await self.db.execute(
            select(RagRecordRef).where(RagRecordRef.id == record_id)
        )
        ref = result.scalar_one_or_none()

        if not ref:
            return None

        # Fetch raw detail
        raw_details = await self._fetch_raw_details([ref.raw_id])
        raw_detail = raw_details.get(ref.raw_id, {})

        # Fetch extracted_text separately (it's large)
        extracted_text = await self._fetch_extracted_text(ref.raw_id)

        return {
            "id": ref.id,
            "raw_id": ref.raw_id,
            "knowledge_id": ref.knowledge_id,
            "context_type": ref.context_type,
            "injection_mode": ref.injection_mode,
            "evaluation_status": ref.evaluation_status,
            "evaluation_result_id": ref.evaluation_result_id,
            "record_date": ref.record_date.isoformat() if ref.record_date else None,
            "name": raw_detail.get("name"),
            "type_data": raw_detail.get("type_data"),
            "extracted_text": extracted_text,
            "created_at": raw_detail.get("created_at"),
        }

    async def _fetch_extracted_text(self, raw_id: int) -> Optional[str]:
        """Fetch extracted_text from Raw DB.

        Args:
            raw_id: Raw record ID

        Returns:
            Extracted text or None
        """
        if not is_raw_db_configured():
            return None

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return None

        async with session_factory() as raw_session:
            query = text("""
                SELECT extracted_text
                FROM subtask_contexts
                WHERE id = :raw_id
            """)

            result = await raw_session.execute(query, {"raw_id": raw_id})
            row = result.fetchone()

            return row.extracted_text if row else None
