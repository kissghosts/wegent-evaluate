"""
RAG Evaluation API endpoints.

These endpoints support the new RagRecordRef-based evaluation architecture.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.rag_evaluation import (
    EvaluationCompareResponse,
    EvaluationTrendsResponse,
    KnowledgeBaseEvaluationStats,
    LowScoreKnowledgeBasesResponse,
    LowScoreKnowledgeBaseItem,
    LowScoreQueriesResponse,
    LowScoreQueryItem,
    RagEvaluationStatusResponse,
    RagEvaluationTriggerRequest,
    RagEvaluationTriggerResponse,
    RagRecordEvaluationDetailResponse,
)
from app.services.rag_evaluation_service import RagEvaluationService

router = APIRouter()


# ============ Evaluation Trigger ============

@router.post("/trigger", response_model=RagEvaluationTriggerResponse)
async def trigger_rag_evaluation(
    request: RagEvaluationTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a new RAG evaluation job.

    Only evaluates records with injection_mode='rag_retrieval'.
    """
    service = RagEvaluationService(db)

    if request.mode == "by_kb" and not request.knowledge_id:
        raise HTTPException(
            status_code=400,
            detail="knowledge_id is required for mode=by_kb",
        )

    job_id, total_records, pending_evaluation = await service.trigger_evaluation(
        mode=request.mode,
        knowledge_id=request.knowledge_id,
        start_date=request.start_date,
        end_date=request.end_date,
        force=request.force,
    )

    # Execute evaluation in background
    background_tasks.add_task(_run_rag_evaluation, job_id)

    return RagEvaluationTriggerResponse(
        job_id=job_id,
        total_records=total_records,
        pending_evaluation=pending_evaluation,
    )


async def _run_rag_evaluation(job_id: str):
    """Background task to run RAG evaluation."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = RagEvaluationService(db)
        await service.execute_evaluation(job_id)


@router.get("/status/{job_id}", response_model=RagEvaluationStatusResponse)
async def get_rag_evaluation_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get status of a RAG evaluation job."""
    service = RagEvaluationService(db)
    job = service.get_job_status(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Evaluation job not found")

    return RagEvaluationStatusResponse(
        job_id=job_id,
        status=job["status"],
        total=job["total"],
        completed=job["completed"],
        failed=job["failed"],
        skipped=job["skipped"],
    )


# ============ Evaluation Trends ============

@router.get("/trends", response_model=EvaluationTrendsResponse)
async def get_evaluation_trends(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    granularity: str = Query("daily", description="Granularity: daily"),
    knowledge_id: Optional[int] = Query(None, description="Filter by knowledge base"),
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation trends over time."""
    service = RagEvaluationService(db)
    result = await service.get_evaluation_trends(
        days=days,
        granularity=granularity,
        knowledge_id=knowledge_id,
    )
    return EvaluationTrendsResponse(**result)


@router.get("/compare", response_model=EvaluationCompareResponse)
async def compare_evaluation_periods(
    period1_start: date = Query(..., description="Period 1 start date"),
    period1_end: date = Query(..., description="Period 1 end date"),
    period2_start: date = Query(..., description="Period 2 start date"),
    period2_end: date = Query(..., description="Period 2 end date"),
    knowledge_id: Optional[int] = Query(None, description="Filter by knowledge base"),
    db: AsyncSession = Depends(get_db),
):
    """Compare evaluation statistics between two time periods."""
    service = RagEvaluationService(db)
    result = await service.compare_periods(
        period1_start=period1_start,
        period1_end=period1_end,
        period2_start=period2_start,
        period2_end=period2_end,
        knowledge_id=knowledge_id,
    )
    return EvaluationCompareResponse(**result)


# ============ Low Score Rankings ============

@router.get("/low-score/queries", response_model=LowScoreQueriesResponse)
async def get_low_score_queries(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    knowledge_id: Optional[int] = Query(None, description="Filter by knowledge base"),
    judgment: str = Query("all", description="Filter by judgment: fail or all"),
    sort_by: str = Query(
        "total_score",
        description="Sort by: total_score, faithfulness_score, trulens_groundedness, ragas_query_context_relevance, trulens_context_relevance",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get low-score queries ranking (sorted by score ascending)."""
    service = RagEvaluationService(db)
    records, total, filters_applied = await service.get_low_score_queries(
        start_date=start_date,
        end_date=end_date,
        knowledge_id=knowledge_id,
        judgment=judgment,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return LowScoreQueriesResponse(
        records=[LowScoreQueryItem(**r) for r in records],
        total=total,
        filters_applied=filters_applied,
    )


@router.get("/low-score/knowledge-bases", response_model=LowScoreKnowledgeBasesResponse)
async def get_low_score_knowledge_bases(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    judgment: str = Query("all", description="Filter by judgment: fail or all"),
    sort_by: str = Query(
        "avg_total_score",
        description="Sort by: avg_total_score, avg_faithfulness, avg_groundedness, avg_query_context_relevance, avg_context_relevance, fail_rate",
    ),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get low-score knowledge bases ranking (sorted by avg score ascending)."""
    service = RagEvaluationService(db)
    knowledge_bases, total = await service.get_low_score_knowledge_bases(
        start_date=start_date,
        end_date=end_date,
        judgment=judgment,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    return LowScoreKnowledgeBasesResponse(
        knowledge_bases=[LowScoreKnowledgeBaseItem(**kb) for kb in knowledge_bases],
        total=total,
    )


# ============ Single Record Evaluation ============

@router.get("/rag-records/{rag_record_ref_id}/evaluation", response_model=RagRecordEvaluationDetailResponse)
async def get_rag_record_evaluation_detail(
    rag_record_ref_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation detail for a single RAG record."""
    service = RagEvaluationService(db)
    result = await service.get_rag_record_evaluation_detail(rag_record_ref_id)

    if not result:
        raise HTTPException(status_code=404, detail="RAG record not found")

    return RagRecordEvaluationDetailResponse(**result)


# ============ Knowledge Base Evaluation Stats ============

@router.get("/knowledge-bases/{kb_id}/evaluation-stats", response_model=KnowledgeBaseEvaluationStats)
async def get_knowledge_base_evaluation_stats(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation statistics for a knowledge base."""
    service = RagEvaluationService(db)
    result = await service.get_kb_evaluation_stats(kb_id)
    return KnowledgeBaseEvaluationStats(**result)
