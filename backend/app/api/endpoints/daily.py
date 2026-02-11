"""
Daily report API endpoints.
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.daily_report_service import DailyReportService
from app.services.raw_sync_service import RawSyncService

router = APIRouter()


# ============ Request/Response Schemas ============

class DailyOverviewResponse(BaseModel):
    """Daily overview response."""
    summary: dict
    comparison: Optional[dict] = None
    daily: list
    start_date: str
    end_date: str


class TrendsResponse(BaseModel):
    """Trends response."""
    granularity: str
    data: list


class HourlyStatsResponse(BaseModel):
    """Hourly stats response."""
    date: str
    hourly: list


class TopKnowledgeBasesResponse(BaseModel):
    """Top knowledge bases response."""
    date: str
    items: list


class KnowledgeBaseListResponse(BaseModel):
    """Knowledge base list response."""
    items: list
    total: int
    page: int
    page_size: int


class KnowledgeBaseDetailResponse(BaseModel):
    """Knowledge base detail response."""
    id: int
    name: Optional[str] = None
    namespace: Optional[str] = None
    kb_type: Optional[str] = None
    is_active: Optional[bool] = None
    created_by_user_id: Optional[int] = None
    created_by_user_name: Optional[str] = None
    retrieval_config: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class KnowledgeBaseStatsResponse(BaseModel):
    """Knowledge base stats response."""
    summary: dict
    daily: list


class QueryListResponse(BaseModel):
    """Query list response."""
    items: list
    total: int
    page: int
    page_size: int


class RagRecordDetailResponse(BaseModel):
    """RAG record detail response."""
    id: int
    raw_id: int
    knowledge_id: Optional[int] = None
    context_type: Optional[str] = None
    injection_mode: Optional[str] = None
    evaluation_status: Optional[str] = None
    evaluation_result_id: Optional[int] = None
    record_date: Optional[str] = None
    name: Optional[str] = None
    type_data: Optional[dict] = None
    extracted_text: Optional[str] = None
    created_at: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    raw_db_configured: bool
    hourly: Optional[dict] = None
    daily: Optional[dict] = None


class SyncTriggerRequest(BaseModel):
    """Sync trigger request."""
    sync_type: str = Field(default="hourly", description="Sync type: hourly, daily, or full")


class SyncTriggerResponse(BaseModel):
    """Sync trigger response."""
    status: str
    message: str
    result: Optional[dict] = None


# ============ Daily Overview Endpoints ============

@router.get("/overview", response_model=DailyOverviewResponse)
async def get_daily_overview(
    start_date: Optional[date] = Query(None, description="Start date (default: 7 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (default: today)"),
    db: AsyncSession = Depends(get_db),
):
    """Get daily overview statistics."""
    service = DailyReportService(db)
    result = await service.get_daily_overview(start_date=start_date, end_date=end_date)
    return DailyOverviewResponse(**result)


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    granularity: str = Query("day", description="Granularity: day or hour"),
    db: AsyncSession = Depends(get_db),
):
    """Get trend data over time."""
    if granularity not in ("day", "hour"):
        raise HTTPException(status_code=400, detail="Invalid granularity. Use 'day' or 'hour'")

    service = DailyReportService(db)
    result = await service.get_trends(days=days, granularity=granularity)
    return TrendsResponse(**result)


@router.get("/{target_date}/hourly", response_model=HourlyStatsResponse)
async def get_hourly_stats(
    target_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Get hourly statistics for a specific date."""
    service = DailyReportService(db)
    hourly = await service.get_hourly_stats(target_date=target_date)
    return HourlyStatsResponse(date=target_date.isoformat(), hourly=hourly)


# ============ Knowledge Base Endpoints ============

@router.get("/knowledge-bases", response_model=KnowledgeBaseListResponse)
async def get_knowledge_bases(
    q: Optional[str] = Query(None, description="Search by id / creator / name / namespace"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated global list of knowledge bases (from Raw DB).

    Results are sorted by recent 7-day usage (descending), then by id (descending).
    """
    service = DailyReportService(db)
    offset = (page - 1) * page_size
    items, total = await service.get_knowledge_base_list(
        q=q,
        limit=page_size,
        offset=offset,
    )
    return KnowledgeBaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/knowledge-bases/top", response_model=TopKnowledgeBasesResponse)
async def get_top_knowledge_bases(
    target_date: Optional[date] = Query(None, description="Date for ranking (default: today)"),
    start_date: Optional[date] = Query(None, description="Start date for range ranking (optional)"),
    end_date: Optional[date] = Query(None, description="End date for range ranking (optional)"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
):
    """Get top knowledge bases by query count.

    - If start_date/end_date provided: return range ranking (sum across dates)
    - Else: return single-day ranking by target_date (default: today)
    """
    service = DailyReportService(db)
    items = await service.get_top_knowledge_bases(
        target_date=target_date,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    # For response `date` field: prioritize explicit target_date; else show end_date/today
    resp_date = (target_date or end_date or date.today()).isoformat()

    return TopKnowledgeBasesResponse(
        date=resp_date,
        items=items,
    )


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseDetailResponse)
async def get_knowledge_base_detail(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge base detail from Raw DB."""
    service = DailyReportService(db)
    result = await service.get_knowledge_base_detail(kb_id)
    if not result:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return KnowledgeBaseDetailResponse(**result)


@router.get("/knowledge-bases/{kb_id}/stats", response_model=KnowledgeBaseStatsResponse)
async def get_knowledge_base_stats(
    kb_id: int,
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a specific knowledge base."""
    service = DailyReportService(db)
    result = await service.get_knowledge_base_stats(kb_id=kb_id, days=days)
    return KnowledgeBaseStatsResponse(**result)


@router.get("/knowledge-bases/{kb_id}/queries", response_model=QueryListResponse)
async def get_knowledge_base_queries(
    kb_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    injection_mode: Optional[str] = Query(None, description="Filter by injection mode"),
    evaluation_status: Optional[str] = Query(None, description="Filter by evaluation status"),
    db: AsyncSession = Depends(get_db),
):
    """Get recent queries for a knowledge base."""
    service = DailyReportService(db)
    offset = (page - 1) * page_size
    items, total = await service.get_knowledge_base_queries(
        kb_id=kb_id,
        limit=page_size,
        offset=offset,
        injection_mode=injection_mode,
        evaluation_status=evaluation_status,
    )
    return QueryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============ Global Query Endpoints ============

@router.get("/queries", response_model=QueryListResponse)
async def get_global_queries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    injection_mode: Optional[str] = Query(None, description="Filter by injection mode (rag_retrieval, direct_injection, selected_documents)"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    db: AsyncSession = Depends(get_db),
):
    """Get global query list (all queries across all knowledge bases).

    Returns queries with associated knowledge base information.
    """
    service = DailyReportService(db)
    offset = (page - 1) * page_size
    items, total = await service.get_global_queries(
        limit=page_size,
        offset=offset,
        injection_mode=injection_mode,
        start_date=start_date,
        end_date=end_date,
    )
    return QueryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============ RAG Record Endpoints ============

@router.get("/rag-records/{record_id}", response_model=RagRecordDetailResponse)
async def get_rag_record_detail(
    record_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed RAG record."""
    service = DailyReportService(db)
    result = await service.get_rag_record_detail(record_id)
    if not result:
        raise HTTPException(status_code=404, detail="RAG record not found")
    return RagRecordDetailResponse(**result)


# ============ Sync Endpoints ============

@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_raw_sync_status(
    db: AsyncSession = Depends(get_db),
):
    """Get raw data sync status."""
    service = RawSyncService(db)
    result = await service.get_sync_status()
    return SyncStatusResponse(**result)


@router.post("/sync/trigger", response_model=SyncTriggerResponse)
async def trigger_raw_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger raw data sync."""
    service = RawSyncService(db)

    if request.sync_type == "hourly":
        result = await service.run_hourly_sync()
    elif request.sync_type == "daily":
        result = await service.run_daily_sync()
    elif request.sync_type == "full":
        # Run both hourly and daily
        hourly_result = await service.run_hourly_sync()
        daily_result = await service.run_daily_sync()
        result = {"hourly": hourly_result, "daily": daily_result}
    else:
        raise HTTPException(status_code=400, detail="Invalid sync_type. Use 'hourly', 'daily', or 'full'")

    return SyncTriggerResponse(
        status=result.get("status", "unknown"),
        message="Sync completed",
        result=result,
    )
