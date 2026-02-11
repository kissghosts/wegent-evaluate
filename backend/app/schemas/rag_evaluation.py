"""
Schemas for RAG evaluation API endpoints (based on RagRecordRef).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============ Trigger Evaluation ============

class RagEvaluationTriggerRequest(BaseModel):
    """Request body for triggering RAG evaluation."""

    mode: Literal["by_kb", "by_date_range"]
    knowledge_id: Optional[int] = None  # Required for mode=by_kb
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    force: bool = False  # Force re-evaluation of completed records


class RagEvaluationTriggerResponse(BaseModel):
    """Response for RAG evaluation trigger endpoint."""

    job_id: str
    total_records: int  # Total rag_retrieval records matching criteria
    pending_evaluation: int  # Number of records to be evaluated


class RagEvaluationStatusResponse(BaseModel):
    """Response for RAG evaluation job status."""

    job_id: str
    status: str  # started, running, completed, failed
    total: int
    completed: int
    failed: int
    skipped: int


# ============ Evaluation Trends ============

class TrendDataPoint(BaseModel):
    """Single data point in trend."""

    date: str
    total_rag_queries: int
    evaluated_count: int
    evaluation_coverage: float
    pass_count: int
    fail_count: int
    undetermined_count: int
    pass_rate: Optional[float] = None
    avg_total_score: Optional[float] = None
    avg_retrieval_score: Optional[float] = None
    avg_generation_score: Optional[float] = None


class TrendComparison(BaseModel):
    """Trend comparison data."""

    pass_rate_change: Optional[float] = None
    avg_score_change: Optional[float] = None


class NonRagStats(BaseModel):
    """Non-RAG usage statistics."""

    direct_injection_count: int
    selected_documents_count: int
    non_rag_ratio: float


class EvaluationTrendsResponse(BaseModel):
    """Response for evaluation trends."""

    trends: List[TrendDataPoint]
    comparison: Optional[Dict[str, TrendComparison]] = None
    non_rag_stats: Optional[NonRagStats] = None


# ============ Period Comparison ============

class PeriodStats(BaseModel):
    """Statistics for a time period."""

    date_range: str
    evaluated_count: int
    pass_rate: Optional[float] = None
    avg_total_score: Optional[float] = None


class PeriodChanges(BaseModel):
    """Changes between two periods."""

    pass_rate_change: Optional[float] = None
    avg_score_change: Optional[float] = None
    improvement: bool = False


class EvaluationCompareResponse(BaseModel):
    """Response for period comparison."""

    period1: PeriodStats
    period2: PeriodStats
    changes: PeriodChanges


# ============ Low Score Rankings ============

class LowScoreQueryItem(BaseModel):
    """Single low-score query item."""

    rag_record_ref_id: int
    raw_id: int
    record_date: Optional[str] = None
    knowledge_id: Optional[int] = None
    knowledge_name: Optional[str] = None
    user_prompt: Optional[str] = None
    evaluation_judgment: Optional[str] = None
    total_score: Optional[float] = None
    faithfulness_score: Optional[float] = None
    trulens_groundedness: Optional[float] = None
    ragas_query_context_relevance: Optional[float] = None
    trulens_context_relevance: Optional[float] = None
    evaluated_at: Optional[datetime] = None


class LowScoreQueriesResponse(BaseModel):
    """Response for low-score queries."""

    records: List[LowScoreQueryItem]
    total: int
    filters_applied: Dict[str, Any]


class LowScoreKnowledgeBaseItem(BaseModel):
    """Single low-score knowledge base item."""

    knowledge_id: int
    knowledge_name: Optional[str] = None
    namespace: Optional[str] = None
    evaluated_count: int
    pass_count: int
    fail_count: int
    undetermined_count: int
    pass_rate: Optional[float] = None
    fail_rate: Optional[float] = None
    avg_total_score: Optional[float] = None
    avg_faithfulness_score: Optional[float] = None
    avg_trulens_groundedness: Optional[float] = None
    avg_ragas_query_context_relevance: Optional[float] = None
    avg_trulens_context_relevance: Optional[float] = None


class LowScoreKnowledgeBasesResponse(BaseModel):
    """Response for low-score knowledge bases."""

    knowledge_bases: List[LowScoreKnowledgeBaseItem]
    total: int


# ============ Single Record Evaluation Detail ============

class CoreMetrics(BaseModel):
    """Core evaluation metrics."""

    faithfulness_score: Optional[float] = None
    trulens_groundedness: Optional[float] = None
    ragas_query_context_relevance: Optional[float] = None
    trulens_context_relevance: Optional[float] = None
    ragas_context_precision_emb: Optional[float] = None


class EvaluationResultData(BaseModel):
    """Evaluation result data."""

    id: int
    evaluation_judgment: Optional[str] = None
    total_score: Optional[float] = None
    retrieval_score: Optional[float] = None
    generation_score: Optional[float] = None
    core_metrics: CoreMetrics
    threshold: float = 0.6
    evaluated_at: Optional[datetime] = None


class RawDataPreview(BaseModel):
    """Raw data preview."""

    user_prompt: Optional[str] = None
    chunks_count: Optional[int] = None
    chunks_preview: Optional[List[str]] = None


class RagRecordEvaluationDetailResponse(BaseModel):
    """Response for single RAG record evaluation detail."""

    rag_record_ref_id: int
    raw_id: int
    evaluation_status: str
    evaluation_result: Optional[EvaluationResultData] = None
    raw_data: Optional[RawDataPreview] = None


# ============ Query List Enhancement ============

class RagQueryItem(BaseModel):
    """Enhanced query item with evaluation info."""

    id: int
    raw_id: int
    record_date: Optional[str] = None
    context_type: Optional[str] = None
    injection_mode: Optional[str] = None
    knowledge_id: Optional[int] = None
    knowledge_name: Optional[str] = None
    namespace: Optional[str] = None
    query: Optional[str] = None
    chunks_count: Optional[int] = None
    created_at: Optional[str] = None

    # Evaluation fields
    is_evaluable: bool = False
    evaluation_status: Optional[str] = None
    evaluation_judgment: Optional[str] = None
    total_score: Optional[float] = None
    evaluated_at: Optional[datetime] = None


class RagQueryListResponse(BaseModel):
    """Response for RAG query list."""

    items: List[RagQueryItem]
    total: int
    page: int
    page_size: int


# ============ Knowledge Base Evaluation Stats ============

class KnowledgeBaseEvaluationStats(BaseModel):
    """Evaluation statistics for a knowledge base."""

    rag_retrieval_count: int
    evaluated_count: int
    evaluation_coverage: float
    pass_count: int
    fail_count: int
    undetermined_count: int
    pass_rate: Optional[float] = None
    avg_total_score: Optional[float] = None
