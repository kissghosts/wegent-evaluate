"""
Service for daily report statistics and analytics.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import func, select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.raw_database import is_raw_db_configured
from app.models import (
    DailyStats,
    HourlyStats,
    InjectionMode,
    KbDailyStats,
    RagRecordRef,
)
from app.services.raw_task_manager_service import RawTaskManagerService

logger = structlog.get_logger(__name__)


class DailyReportService:
    """Service for daily report queries and analytics."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session.

        Args:
            db: Local database session
        """
        self.db = db
        self.raw_tm = RawTaskManagerService(db)

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
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get top knowledge bases by query count.

        支持两种模式：
        1) 单日榜单：仅传 target_date（默认 today）
        2) 区间榜单：传 start_date/end_date（任一存在即启用），按区间内累计 total_queries 排序

        返回 items 会尽量补齐：knowledge_name / namespace / created_by_user_id / created_by_user_name。
        """

        # Range mode
        if start_date is not None or end_date is not None:
            if end_date is None:
                end_date = date.today()
            if start_date is None:
                start_date = end_date - timedelta(days=6)

            stmt = (
                select(
                    KbDailyStats.knowledge_id.label("knowledge_id"),
                    func.max(KbDailyStats.knowledge_name).label("knowledge_name"),
                    func.max(KbDailyStats.namespace).label("namespace"),
                    func.sum(KbDailyStats.total_queries).label("total_queries"),
                    func.sum(KbDailyStats.rag_retrieval_count).label("rag_retrieval_count"),
                    func.sum(KbDailyStats.direct_injection_count).label("direct_injection_count"),
                    func.sum(KbDailyStats.selected_documents_count).label("selected_documents_count"),
                )
                .where(KbDailyStats.date >= start_date, KbDailyStats.date <= end_date)
                .group_by(KbDailyStats.knowledge_id)
                .order_by(func.sum(KbDailyStats.total_queries).desc())
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            items: List[Dict[str, Any]] = []
            for idx, row in enumerate(rows):
                items.append(
                    {
                        "rank": idx + 1,
                        "knowledge_id": row.knowledge_id,
                        "knowledge_name": row.knowledge_name,
                        "namespace": row.namespace,
                        "total_queries": int(row.total_queries or 0),
                        "rag_retrieval_count": int(row.rag_retrieval_count or 0),
                        "direct_injection_count": int(row.direct_injection_count or 0),
                        "selected_documents_count": int(row.selected_documents_count or 0),
                        "primary_mode": self._get_primary_mode_from_counts(
                            rag=int(row.rag_retrieval_count or 0),
                            direct=int(row.direct_injection_count or 0),
                            selected=int(row.selected_documents_count or 0),
                        ),
                    }
                )

            await self._enrich_kb_items(items)
            return items

        # Single-day mode (backward compatible)
        if target_date is None:
            target_date = date.today()

        result = await self.db.execute(
            select(KbDailyStats)
            .where(KbDailyStats.date == target_date)
            .order_by(KbDailyStats.total_queries.desc())
            .limit(limit)
        )
        kb_stats = result.scalars().all()

        items = [
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

        await self._enrich_kb_items(items)
        return items

    def _get_primary_mode_from_counts(self, rag: int, direct: int, selected: int) -> str:
        modes = {
            "rag_retrieval": rag,
            "direct_injection": direct,
            "selected_documents": selected,
        }
        return max(modes, key=modes.get)

    def _get_primary_mode(self, kb: KbDailyStats) -> str:
        """Determine primary usage mode for a knowledge base."""
        return self._get_primary_mode_from_counts(
            rag=kb.rag_retrieval_count,
            direct=kb.direct_injection_count,
            selected=kb.selected_documents_count,
        )

    async def _enrich_kb_items(self, items: List[Dict[str, Any]]) -> None:
        """Enrich KB items with name/namespace and creator from Raw DB.

        This avoids UI fallback names like KB-25 when cached fields are null.
        """
        if not items:
            return

        kb_ids: List[int] = []
        for it in items:
            kb_id = it.get("knowledge_id")
            if kb_id is None:
                continue
            try:
                kb_ids.append(int(kb_id))
            except Exception:
                continue

        if not kb_ids:
            return

        kb_meta = await self.raw_tm.fetch_kb_metas(kb_ids)
        user_ids = [m.get("created_by_user_id") for m in kb_meta.values() if m.get("created_by_user_id")]
        user_names = await self.raw_tm.fetch_user_names([int(u) for u in user_ids if u is not None])

        for it in items:
            kb_id = it.get("knowledge_id")
            if kb_id is None:
                continue

            meta = kb_meta.get(int(kb_id))
            if not meta:
                continue

            it["knowledge_name"] = it.get("knowledge_name") or meta.get("knowledge_name")
            it["namespace"] = it.get("namespace") or meta.get("namespace")

            created_by_id = meta.get("created_by_user_id")
            it["created_by_user_id"] = created_by_id
            it["created_by_user_name"] = user_names.get(int(created_by_id)) if created_by_id else None

    async def get_knowledge_base_list(
        self,
        q: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated knowledge base list (global list from Raw DB).

        Used by the left sidebar navigation page `/knowledge-bases`.

        注意：
        - Raw DB 提供"目录信息"（名称/namespace/creator/描述/类型/创建时间等）
        - "最近 7 天是否使用 / 查询量"来自本地统计表 `kb_daily_stats` 的聚合
        - 排序逻辑：按最近7天使用数量倒序，未使用的按id倒序

        Args:
            q: Search keyword (id / creator id / name / namespace / creator user_name)
            limit: Page size
            offset: Offset

        Returns:
            (items, total)
        """
        # Get all matching items from Raw DB (no pagination at raw level, we sort in memory)
        all_items, total = await self.raw_tm.list_knowledge_bases(
            limit=10000,  # Get all for sorting
            offset=0,
            q=q,
        )

        # Collect all kb_ids
        kb_ids: List[int] = []
        for it in all_items:
            kb_id = it.get("knowledge_id")
            if kb_id is None:
                continue
            try:
                kb_ids.append(int(kb_id))
            except Exception:
                continue

        # Get recent 7d usage from local stats
        recent_by_kb: Dict[int, int] = {}
        if kb_ids:
            end_date = date.today()
            start_date = end_date - timedelta(days=6)

            result = await self.db.execute(
                select(
                    KbDailyStats.knowledge_id.label("knowledge_id"),
                    func.sum(KbDailyStats.total_queries).label("total_queries"),
                )
                .where(
                    KbDailyStats.knowledge_id.in_(kb_ids),
                    KbDailyStats.date >= start_date,
                    KbDailyStats.date <= end_date,
                )
                .group_by(KbDailyStats.knowledge_id)
            )
            for row in result.all():
                recent_by_kb[int(row.knowledge_id)] = int(row.total_queries or 0)

        # Build normalized items with usage stats
        normalized: List[Dict[str, Any]] = []
        for it in all_items:
            kb_id = it.get("knowledge_id")
            kb_id_int = int(kb_id) if kb_id is not None else None
            recent_7d_queries = recent_by_kb.get(kb_id_int, 0) if kb_id_int is not None else 0

            normalized.append(
                {
                    "knowledge_id": it.get("knowledge_id"),
                    "knowledge_name": it.get("knowledge_name"),
                    "namespace": it.get("namespace"),
                    "created_by_user_id": it.get("created_by_user_id"),
                    "created_by_user_name": it.get("created_by_user_name"),
                    "description": it.get("description"),
                    "kb_type": it.get("kb_type"),
                    "created_at": it.get("created_at"),
                    "updated_at": it.get("updated_at"),
                    "recent_7d_queries": recent_7d_queries,
                    "recent_7d_used": recent_7d_queries > 0,
                    "total_queries": 0,
                    "rag_retrieval_count": 0,
                    "direct_injection_count": 0,
                    "selected_documents_count": 0,
                }
            )

        # Sort by recent_7d_queries DESC, then by knowledge_id DESC
        normalized.sort(
            key=lambda x: (-x.get("recent_7d_queries", 0), -(x.get("knowledge_id") or 0))
        )

        # Apply pagination
        paginated = normalized[offset:offset + limit]

        return paginated, total

    async def get_knowledge_base_stats(
        self,
        kb_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get statistics for a specific knowledge base."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

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

        latest = kb_stats[-1] if kb_stats else None

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
        """Get knowledge base detail from Raw DB (including creator info)."""
        return await self.raw_tm.get_kb_detail(kb_id)

    async def get_knowledge_base_queries(
        self,
        kb_id: int,
        limit: int = 20,
        offset: int = 0,
        injection_mode: Optional[str] = None,
        evaluation_status: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get recent queries for a knowledge base."""
        conditions = [RagRecordRef.knowledge_id == kb_id]
        if injection_mode:
            conditions.append(RagRecordRef.injection_mode == injection_mode)
        if evaluation_status:
            conditions.append(RagRecordRef.evaluation_status == evaluation_status)

        count_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

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

        raw_ids = [ref.raw_id for ref in refs]
        raw_details = await self.raw_tm.fetch_subtask_context_details(raw_ids)

        # Fetch evaluation results for refs that have them
        eval_result_ids = [ref.evaluation_result_id for ref in refs if ref.evaluation_result_id]
        eval_results_map = {}
        if eval_result_ids:
            from app.models import EvaluationResult
            eval_query = await self.db.execute(
                select(EvaluationResult).where(EvaluationResult.id.in_(eval_result_ids))
            )
            for er in eval_query.scalars().all():
                eval_results_map[er.id] = er

        queries: List[Dict[str, Any]] = []
        for ref in refs:
            raw_detail = raw_details.get(ref.raw_id, {})
            rag_result = raw_detail.get("type_data", {}).get("rag_result", {})
            eval_result = eval_results_map.get(ref.evaluation_result_id) if ref.evaluation_result_id else None

            # Determine if this record is evaluable (only rag_retrieval is evaluable)
            is_evaluable = ref.injection_mode == InjectionMode.RAG_RETRIEVAL.value

            queries.append(
                {
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
                    # Evaluation fields
                    "is_evaluable": is_evaluable,
                    "evaluation_judgment": eval_result.evaluation_judgment if eval_result else None,
                    "total_score": eval_result.total_score if eval_result else None,
                    "evaluated_at": ref.evaluated_at.isoformat() if ref.evaluated_at else None,
                }
            )

        return queries, total

    async def _fetch_raw_details(self, raw_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Backward-compatible wrapper."""
        return await self.raw_tm.fetch_subtask_context_details(raw_ids)

    async def get_rag_record_detail(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed RAG record by local ID."""
        result = await self.db.execute(select(RagRecordRef).where(RagRecordRef.id == record_id))
        ref = result.scalar_one_or_none()
        if not ref:
            return None

        raw_details = await self.raw_tm.fetch_subtask_context_details([ref.raw_id])
        raw_detail = raw_details.get(ref.raw_id, {})
        extracted_text = await self.raw_tm.fetch_extracted_text(ref.raw_id)

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
        """Fetch extracted_text from Raw DB."""
        return await self.raw_tm.fetch_extracted_text(raw_id)

    async def get_global_queries(
        self,
        limit: int = 20,
        offset: int = 0,
        injection_mode: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        evaluation_status: Optional[str] = None,
        evaluation_judgment: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get global query list (not filtered by knowledge base).

        Args:
            limit: Page size
            offset: Offset
            injection_mode: Optional filter by injection mode
            start_date: Optional start date filter
            end_date: Optional end date filter
            evaluation_status: Optional filter by evaluation status
            evaluation_judgment: Optional filter by evaluation judgment (pass/fail/undetermined)

        Returns:
            (items, total)
        """
        conditions = []
        if injection_mode:
            conditions.append(RagRecordRef.injection_mode == injection_mode)
        if start_date:
            conditions.append(RagRecordRef.record_date >= start_date)
        if end_date:
            conditions.append(RagRecordRef.record_date <= end_date)
        if evaluation_status:
            conditions.append(RagRecordRef.evaluation_status == evaluation_status)

        # For evaluation_judgment filter, we need to join with EvaluationResult
        join_eval = evaluation_judgment is not None

        # Count total
        if join_eval:
            from app.models import EvaluationResult
            count_stmt = (
                select(func.count(RagRecordRef.id))
                .join(EvaluationResult, RagRecordRef.evaluation_result_id == EvaluationResult.id)
                .where(EvaluationResult.evaluation_judgment == evaluation_judgment)
            )
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))
        else:
            count_stmt = select(func.count(RagRecordRef.id))
            if conditions:
                count_stmt = count_stmt.where(and_(*conditions))

        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Fetch records
        stmt = select(RagRecordRef).order_by(
            RagRecordRef.record_date.desc(),
            RagRecordRef.id.desc()
        ).offset(offset).limit(limit)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        if join_eval:
            from app.models import EvaluationResult
            stmt = (
                select(RagRecordRef)
                .join(EvaluationResult, RagRecordRef.evaluation_result_id == EvaluationResult.id)
                .where(EvaluationResult.evaluation_judgment == evaluation_judgment)
                .order_by(RagRecordRef.record_date.desc(), RagRecordRef.id.desc())
                .offset(offset)
                .limit(limit)
            )
            if conditions:
                stmt = stmt.where(and_(*conditions))

        result = await self.db.execute(stmt)
        refs = result.scalars().all()

        if not refs:
            return [], total

        # Fetch raw details
        raw_ids = [ref.raw_id for ref in refs]
        raw_details = await self.raw_tm.fetch_subtask_context_details(raw_ids)

        # Fetch KB metadata for all unique knowledge_ids
        kb_ids = list({ref.knowledge_id for ref in refs if ref.knowledge_id is not None})
        kb_metas = await self.raw_tm.fetch_kb_metas(kb_ids) if kb_ids else {}

        # Fetch evaluation results for refs that have them
        eval_result_ids = [ref.evaluation_result_id for ref in refs if ref.evaluation_result_id]
        eval_results_map = {}
        if eval_result_ids:
            from app.models import EvaluationResult
            eval_query = await self.db.execute(
                select(EvaluationResult).where(EvaluationResult.id.in_(eval_result_ids))
            )
            for er in eval_query.scalars().all():
                eval_results_map[er.id] = er

        queries: List[Dict[str, Any]] = []
        for ref in refs:
            raw_detail = raw_details.get(ref.raw_id, {})
            rag_result = raw_detail.get("type_data", {}).get("rag_result", {})

            # Get KB metadata
            kb_meta = kb_metas.get(ref.knowledge_id, {}) if ref.knowledge_id else {}

            # Get evaluation result
            eval_result = eval_results_map.get(ref.evaluation_result_id) if ref.evaluation_result_id else None

            # Determine if this record is evaluable (only rag_retrieval is evaluable)
            is_evaluable = ref.injection_mode == InjectionMode.RAG_RETRIEVAL.value

            queries.append(
                {
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
                    # KB info
                    "knowledge_id": ref.knowledge_id,
                    "knowledge_name": kb_meta.get("knowledge_name"),
                    "namespace": kb_meta.get("namespace"),
                    # Evaluation fields
                    "is_evaluable": is_evaluable,
                    "evaluation_judgment": eval_result.evaluation_judgment if eval_result else None,
                    "total_score": eval_result.total_score if eval_result else None,
                    "evaluated_at": ref.evaluated_at.isoformat() if ref.evaluated_at else None,
                }
            )

        return queries, total
