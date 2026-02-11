"""
Service for RAG evaluation based on RagRecordRef architecture.

This service handles evaluation of RAG records directly from raw DB,
replacing the old ConversationRecord-based evaluation flow.
"""

import asyncio
import math
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    EvaluationResult,
    InjectionMode,
    RagRecordEvaluationStatus,
    RagRecordRef,
)
from app.services.cross_validation import cross_validation_service
from app.services.diagnostic_analyzer import diagnostic_analyzer
from app.services.ragas import (
    embedding_metrics_evaluator,
    llm_metrics_evaluator,
    ragas_evaluator,
)
from app.services.raw_task_manager_service import RawTaskManagerService
from app.services.trulens import trulens_embedding_evaluator, trulens_llm_evaluator

logger = structlog.get_logger(__name__)


# In-memory job tracking
rag_evaluation_jobs: Dict[str, Dict[str, Any]] = {}


def sanitize_float(value: Any) -> Optional[float]:
    """Sanitize a float value for MySQL storage."""
    if value is None:
        return None
    try:
        float_val = float(value)
        if math.isnan(float_val) or math.isinf(float_val):
            return None
        return float_val
    except (TypeError, ValueError):
        return None


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize a dictionary."""
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = [
                (
                    sanitize_dict(item)
                    if isinstance(item, dict)
                    else sanitize_float(item) if isinstance(item, float) else item
                )
                for item in value
            ]
        elif isinstance(value, float):
            result[key] = sanitize_float(value)
        else:
            result[key] = value
    return result


class RagEvaluationService:
    """Service for evaluating RAG records based on RagRecordRef."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.raw_tm = RawTaskManagerService(db)

    async def trigger_evaluation(
        self,
        mode: str,
        knowledge_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
    ) -> Tuple[str, int, int]:
        """
        Trigger a new RAG evaluation job.

        Args:
            mode: 'by_kb' or 'by_date_range'
            knowledge_id: Required for mode=by_kb
            start_date: Start date filter
            end_date: End date filter
            force: Re-evaluate completed records

        Returns:
            (job_id, total_records, pending_evaluation)
        """
        job_id = str(uuid.uuid4())

        # Build query for rag_retrieval records only
        conditions = [RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value]

        if mode == "by_kb" and knowledge_id:
            conditions.append(RagRecordRef.knowledge_id == knowledge_id)

        if start_date:
            conditions.append(RagRecordRef.record_date >= start_date)
        if end_date:
            conditions.append(RagRecordRef.record_date <= end_date)

        if not force:
            # Only evaluate pending or failed records
            conditions.append(
                RagRecordRef.evaluation_status.in_([
                    RagRecordEvaluationStatus.PENDING.value,
                    RagRecordEvaluationStatus.FAILED.value,
                ])
            )

        query = select(RagRecordRef).where(and_(*conditions))
        result = await self.db.execute(query)
        records = result.scalars().all()

        total_records = len(records)
        pending_evaluation = len([r for r in records if r.evaluation_status != RagRecordEvaluationStatus.COMPLETED.value])

        # Store job info
        rag_evaluation_jobs[job_id] = {
            "status": "started",
            "total": total_records,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "record_ids": [r.id for r in records],
        }

        return job_id, total_records, pending_evaluation

    async def execute_evaluation(self, job_id: str) -> None:
        """Execute the RAG evaluation job."""
        if job_id not in rag_evaluation_jobs:
            logger.error("RAG evaluation job not found", job_id=job_id)
            return

        job = rag_evaluation_jobs[job_id]
        job["status"] = "running"

        record_ids = job["record_ids"]

        for record_id in record_ids:
            try:
                await self._evaluate_single_rag_record(record_id)
                job["completed"] += 1
            except Exception as e:
                logger.exception(
                    "Failed to evaluate RAG record", record_id=record_id, error=str(e)
                )
                job["failed"] += 1

        job["status"] = "completed"
        logger.info(
            "RAG evaluation job completed",
            job_id=job_id,
            completed=job["completed"],
            failed=job["failed"],
        )

    async def _evaluate_single_rag_record(self, rag_ref_id: int) -> None:
        """Evaluate a single RAG record."""
        start_time = time.time()

        # Get RagRecordRef
        result = await self.db.execute(
            select(RagRecordRef).where(RagRecordRef.id == rag_ref_id)
        )
        rag_ref = result.scalar_one_or_none()

        if not rag_ref:
            logger.warning("RagRecordRef not found", rag_ref_id=rag_ref_id)
            return

        if rag_ref.injection_mode != InjectionMode.RAG_RETRIEVAL.value:
            logger.warning(
                "Skipping non-rag_retrieval record",
                rag_ref_id=rag_ref_id,
                mode=rag_ref.injection_mode,
            )
            rag_ref.evaluation_status = RagRecordEvaluationStatus.SKIPPED.value
            await self.db.commit()
            return

        try:
            # Fetch raw data from Raw DB
            raw_details = await self.raw_tm.fetch_subtask_context_details([rag_ref.raw_id])
            raw_detail = raw_details.get(rag_ref.raw_id, {})
            type_data = raw_detail.get("type_data", {})
            rag_result = type_data.get("rag_result", {})

            # Extract evaluation inputs
            user_prompt = rag_result.get("query", "")
            extracted_text = await self.raw_tm.fetch_extracted_text(rag_ref.raw_id)

            if not extracted_text:
                logger.warning(
                    "No extracted text for RAG record",
                    rag_ref_id=rag_ref_id,
                    raw_id=rag_ref.raw_id,
                )
                rag_ref.evaluation_status = RagRecordEvaluationStatus.SKIPPED.value
                await self.db.commit()
                return

            # Get assistant answer from chunks if available
            chunks = rag_result.get("chunks", [])
            assistant_answer = "\n".join([
                c.get("text", "") for c in chunks if c.get("text")
            ]) if chunks else extracted_text

            # Update status to processing
            rag_ref.evaluation_status = RagRecordEvaluationStatus.PENDING.value
            await self.db.commit()

            # Prepare contexts list
            contexts = [extracted_text]

            # Run evaluations in parallel
            (
                ragas_result,
                ragas_emb_result,
                ragas_llm_ext_result,
                trulens_emb_result,
                trulens_llm_result,
            ) = await asyncio.gather(
                ragas_evaluator.evaluate(
                    user_prompt=user_prompt,
                    assistant_answer=assistant_answer,
                    extracted_text=extracted_text,
                ),
                embedding_metrics_evaluator.evaluate_all(
                    query=user_prompt,
                    contexts=contexts,
                ),
                llm_metrics_evaluator.evaluate_all(
                    question=user_prompt,
                    context=extracted_text,
                    answer=assistant_answer,
                ),
                trulens_embedding_evaluator.evaluate_all(
                    query=user_prompt,
                    contexts=contexts,
                    answer=assistant_answer,
                ),
                trulens_llm_evaluator.evaluate_all(
                    question=user_prompt,
                    context=extracted_text,
                    answer=assistant_answer,
                ),
                return_exceptions=True,
            )

            # Handle exceptions in results
            if isinstance(ragas_result, Exception):
                logger.error("RAGAS evaluation failed", error=str(ragas_result))
                ragas_result = {
                    "faithfulness_score": None,
                    "answer_relevancy_score": None,
                    "context_precision_score": None,
                    "overall_score": None,
                    "raw_result": None,
                }

            if isinstance(ragas_emb_result, Exception):
                logger.error("RAGAS embedding metrics failed", error=str(ragas_emb_result))
                ragas_emb_result = {
                    "query_context_relevance": None,
                    "context_precision_emb": None,
                    "context_diversity": None,
                }

            if isinstance(ragas_llm_ext_result, Exception):
                logger.error("RAGAS LLM extended metrics failed", error=str(ragas_llm_ext_result))
                ragas_llm_ext_result = {
                    "context_utilization": None,
                    "coherence": None,
                }

            if isinstance(trulens_emb_result, Exception):
                logger.error("TruLens embedding metrics failed", error=str(trulens_emb_result))
                trulens_emb_result = {
                    "context_relevance": None,
                    "relevance_embedding": None,
                }

            if isinstance(trulens_llm_result, Exception):
                logger.error("TruLens LLM metrics failed", error=str(trulens_llm_result))
                trulens_llm_result = {
                    "groundedness": None,
                    "relevance_llm": None,
                    "coherence": None,
                    "harmlessness": None,
                }

            # Cross-validation
            ragas_metrics = {
                "faithfulness_score": ragas_result.get("faithfulness_score"),
                "answer_relevancy_score": ragas_result.get("answer_relevancy_score"),
                "context_precision_score": ragas_result.get("context_precision_score"),
                "ragas_query_context_relevance": ragas_emb_result.get("query_context_relevance"),
                "ragas_context_precision_emb": ragas_emb_result.get("context_precision_emb"),
                "ragas_context_diversity": ragas_emb_result.get("context_diversity"),
                "ragas_context_utilization": ragas_llm_ext_result.get("context_utilization"),
                "ragas_coherence": ragas_llm_ext_result.get("coherence"),
            }

            trulens_metrics = {
                "trulens_context_relevance": trulens_emb_result.get("context_relevance"),
                "trulens_relevance_embedding": trulens_emb_result.get("relevance_embedding"),
                "trulens_groundedness": trulens_llm_result.get("groundedness"),
                "trulens_relevance_llm": trulens_llm_result.get("relevance_llm"),
                "trulens_coherence": trulens_llm_result.get("coherence"),
                "trulens_harmlessness": trulens_llm_result.get("harmlessness"),
            }

            cv_result = cross_validation_service.validate(ragas_metrics, trulens_metrics)

            # Generate diagnostic analyses
            diagnostic_results = await diagnostic_analyzer.analyze_all(
                ragas_metrics=ragas_metrics,
                trulens_metrics=trulens_metrics,
                cross_validation_results=cv_result,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Sanitize results
            sanitized_cv_result = sanitize_dict(cv_result) if cv_result else None
            sanitized_ragas_analysis = (
                sanitize_dict(diagnostic_results.get("ragas_analysis"))
                if diagnostic_results.get("ragas_analysis")
                else None
            )
            sanitized_trulens_analysis = (
                sanitize_dict(diagnostic_results.get("trulens_analysis"))
                if diagnostic_results.get("trulens_analysis")
                else None
            )
            sanitized_overall_analysis = (
                sanitize_dict(diagnostic_results.get("overall_analysis"))
                if diagnostic_results.get("overall_analysis")
                else None
            )

            # Create or update evaluation result
            existing_result = await self.db.execute(
                select(EvaluationResult).where(
                    EvaluationResult.rag_record_ref_id == rag_ref_id
                )
            )
            evaluation = existing_result.scalar_one_or_none()

            if evaluation:
                # Update existing evaluation
                self._update_evaluation_result(
                    evaluation,
                    ragas_result,
                    ragas_emb_result,
                    ragas_llm_ext_result,
                    trulens_emb_result,
                    trulens_llm_result,
                    sanitized_cv_result,
                    {
                        "ragas_analysis": sanitized_ragas_analysis,
                        "trulens_analysis": sanitized_trulens_analysis,
                        "overall_analysis": sanitized_overall_analysis,
                    },
                    duration_ms,
                )
            else:
                # Create new evaluation
                evaluation = EvaluationResult(
                    rag_record_ref_id=rag_ref_id,
                    # Legacy fields set to None
                    conversation_record_id=None,
                    version_id=None,
                    # RAGAS scores
                    faithfulness_score=sanitize_float(ragas_result.get("faithfulness_score")),
                    answer_relevancy_score=sanitize_float(ragas_result.get("answer_relevancy_score")),
                    context_precision_score=sanitize_float(ragas_result.get("context_precision_score")),
                    overall_score=sanitize_float(ragas_result.get("overall_score")),
                    # RAGAS Embedding metrics
                    ragas_query_context_relevance=sanitize_float(ragas_emb_result.get("query_context_relevance")),
                    ragas_context_precision_emb=sanitize_float(ragas_emb_result.get("context_precision_emb")),
                    ragas_context_diversity=sanitize_float(ragas_emb_result.get("context_diversity")),
                    # RAGAS LLM metrics
                    ragas_context_utilization=sanitize_float(ragas_llm_ext_result.get("context_utilization")),
                    ragas_coherence=sanitize_float(ragas_llm_ext_result.get("coherence")),
                    # TruLens Embedding metrics
                    trulens_context_relevance=sanitize_float(trulens_emb_result.get("context_relevance")),
                    trulens_relevance_embedding=sanitize_float(trulens_emb_result.get("relevance_embedding")),
                    # TruLens LLM metrics
                    trulens_groundedness=sanitize_float(trulens_llm_result.get("groundedness")),
                    trulens_relevance_llm=sanitize_float(trulens_llm_result.get("relevance_llm")),
                    trulens_coherence=sanitize_float(trulens_llm_result.get("coherence")),
                    trulens_harmlessness=sanitize_float(trulens_llm_result.get("harmlessness")),
                    # Cross-validation
                    cross_validation_results=sanitized_cv_result,
                    has_cross_validation_alert=sanitized_cv_result.get("has_alert", False) if sanitized_cv_result else False,
                    # Diagnostic analyses
                    ragas_analysis=sanitized_ragas_analysis,
                    trulens_analysis=sanitized_trulens_analysis,
                    overall_analysis=sanitized_overall_analysis,
                    # Metadata
                    evaluation_model=settings.RAGAS_LLM_MODEL,
                    evaluation_duration_ms=duration_ms,
                )
                self.db.add(evaluation)

            # Calculate tiered scores
            evaluation.calculate_tiered_scores()

            await self.db.flush()

            # Update RagRecordRef
            rag_ref.evaluation_result_id = evaluation.id
            rag_ref.evaluation_status = RagRecordEvaluationStatus.COMPLETED.value
            rag_ref.evaluated_at = datetime.utcnow()

            await self.db.commit()

            logger.info(
                "RAG record evaluated successfully",
                rag_ref_id=rag_ref_id,
                total_score=evaluation.total_score,
                judgment=evaluation.evaluation_judgment,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.exception("RAG evaluation failed", rag_ref_id=rag_ref_id, error=str(e))
            rag_ref.evaluation_status = RagRecordEvaluationStatus.FAILED.value
            await self.db.commit()
            raise

    def _update_evaluation_result(
        self,
        evaluation: EvaluationResult,
        ragas_result: Dict,
        ragas_emb_result: Dict,
        ragas_llm_ext_result: Dict,
        trulens_emb_result: Dict,
        trulens_llm_result: Dict,
        cv_result: Dict,
        diagnostic_results: Dict,
        duration_ms: int,
    ) -> None:
        """Update an existing evaluation result."""
        evaluation.faithfulness_score = sanitize_float(ragas_result.get("faithfulness_score"))
        evaluation.answer_relevancy_score = sanitize_float(ragas_result.get("answer_relevancy_score"))
        evaluation.context_precision_score = sanitize_float(ragas_result.get("context_precision_score"))
        evaluation.overall_score = sanitize_float(ragas_result.get("overall_score"))

        evaluation.ragas_query_context_relevance = sanitize_float(ragas_emb_result.get("query_context_relevance"))
        evaluation.ragas_context_precision_emb = sanitize_float(ragas_emb_result.get("context_precision_emb"))
        evaluation.ragas_context_diversity = sanitize_float(ragas_emb_result.get("context_diversity"))

        evaluation.ragas_context_utilization = sanitize_float(ragas_llm_ext_result.get("context_utilization"))
        evaluation.ragas_coherence = sanitize_float(ragas_llm_ext_result.get("coherence"))

        evaluation.trulens_context_relevance = sanitize_float(trulens_emb_result.get("context_relevance"))
        evaluation.trulens_relevance_embedding = sanitize_float(trulens_emb_result.get("relevance_embedding"))

        evaluation.trulens_groundedness = sanitize_float(trulens_llm_result.get("groundedness"))
        evaluation.trulens_relevance_llm = sanitize_float(trulens_llm_result.get("relevance_llm"))
        evaluation.trulens_coherence = sanitize_float(trulens_llm_result.get("coherence"))
        evaluation.trulens_harmlessness = sanitize_float(trulens_llm_result.get("harmlessness"))

        evaluation.cross_validation_results = cv_result
        evaluation.has_cross_validation_alert = cv_result.get("has_alert", False) if cv_result else False

        evaluation.ragas_analysis = diagnostic_results.get("ragas_analysis")
        evaluation.trulens_analysis = diagnostic_results.get("trulens_analysis")
        evaluation.overall_analysis = diagnostic_results.get("overall_analysis")

        evaluation.evaluation_model = settings.RAGAS_LLM_MODEL
        evaluation.evaluation_duration_ms = duration_ms
        evaluation.created_at = datetime.utcnow()

        evaluation.calculate_tiered_scores()

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a RAG evaluation job."""
        return rag_evaluation_jobs.get(job_id)

    async def get_evaluation_trends(
        self,
        days: int = 7,
        granularity: str = "daily",
        knowledge_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get evaluation trends over time."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        trends = []
        non_rag_direct = 0
        non_rag_selected = 0
        total_records = 0

        for i in range(days):
            current_date = start_date + timedelta(days=i)

            # Build conditions
            conditions = [RagRecordRef.record_date == current_date]
            if knowledge_id:
                conditions.append(RagRecordRef.knowledge_id == knowledge_id)

            # Count total RAG queries for the day
            rag_conditions = conditions + [RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value]
            rag_count_result = await self.db.execute(
                select(func.count(RagRecordRef.id)).where(and_(*rag_conditions))
            )
            total_rag_queries = rag_count_result.scalar() or 0

            # Count evaluated records
            evaluated_conditions = rag_conditions + [
                RagRecordRef.evaluation_status == RagRecordEvaluationStatus.COMPLETED.value
            ]
            evaluated_result = await self.db.execute(
                select(func.count(RagRecordRef.id)).where(and_(*evaluated_conditions))
            )
            evaluated_count = evaluated_result.scalar() or 0

            # Get evaluation results for the day
            eval_query = (
                select(
                    func.count(EvaluationResult.id).label("count"),
                    func.sum(case((EvaluationResult.evaluation_judgment == "pass", 1), else_=0)).label("pass_count"),
                    func.sum(case((EvaluationResult.evaluation_judgment == "fail", 1), else_=0)).label("fail_count"),
                    func.sum(case((EvaluationResult.evaluation_judgment == "undetermined", 1), else_=0)).label("undetermined_count"),
                    func.avg(EvaluationResult.total_score).label("avg_total_score"),
                    func.avg(EvaluationResult.retrieval_score).label("avg_retrieval_score"),
                    func.avg(EvaluationResult.generation_score).label("avg_generation_score"),
                )
                .join(RagRecordRef, RagRecordRef.evaluation_result_id == EvaluationResult.id)
                .where(and_(*rag_conditions))
            )
            eval_result = await self.db.execute(eval_query)
            eval_row = eval_result.fetchone()

            pass_count = int(eval_row.pass_count or 0) if eval_row else 0
            fail_count = int(eval_row.fail_count or 0) if eval_row else 0
            undetermined_count = int(eval_row.undetermined_count or 0) if eval_row else 0

            trends.append({
                "date": current_date.isoformat(),
                "total_rag_queries": total_rag_queries,
                "evaluated_count": evaluated_count,
                "evaluation_coverage": evaluated_count / total_rag_queries if total_rag_queries > 0 else 0,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "undetermined_count": undetermined_count,
                "pass_rate": pass_count / evaluated_count if evaluated_count > 0 else None,
                "avg_total_score": float(eval_row.avg_total_score) if eval_row and eval_row.avg_total_score else None,
                "avg_retrieval_score": float(eval_row.avg_retrieval_score) if eval_row and eval_row.avg_retrieval_score else None,
                "avg_generation_score": float(eval_row.avg_generation_score) if eval_row and eval_row.avg_generation_score else None,
            })

            total_records += total_rag_queries

        # Count non-RAG records
        non_rag_conditions = [
            RagRecordRef.record_date >= start_date,
            RagRecordRef.record_date <= end_date,
        ]
        if knowledge_id:
            non_rag_conditions.append(RagRecordRef.knowledge_id == knowledge_id)

        direct_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(
                and_(*non_rag_conditions, RagRecordRef.injection_mode == InjectionMode.DIRECT_INJECTION.value)
            )
        )
        non_rag_direct = direct_result.scalar() or 0

        selected_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(
                and_(*non_rag_conditions, RagRecordRef.context_type == "selected_documents")
            )
        )
        non_rag_selected = selected_result.scalar() or 0

        total_all = total_records + non_rag_direct + non_rag_selected

        # Calculate comparisons
        comparison = {}
        if len(trends) >= 2:
            today = trends[-1]
            yesterday = trends[-2]
            if yesterday.get("pass_rate") is not None and today.get("pass_rate") is not None:
                comparison["day_over_day"] = {
                    "pass_rate_change": today["pass_rate"] - yesterday["pass_rate"],
                    "avg_score_change": (today.get("avg_total_score") or 0) - (yesterday.get("avg_total_score") or 0),
                }

        if len(trends) >= 8:
            this_week = trends[-1]
            last_week = trends[-8]
            if last_week.get("pass_rate") is not None and this_week.get("pass_rate") is not None:
                comparison["week_over_week"] = {
                    "pass_rate_change": this_week["pass_rate"] - last_week["pass_rate"],
                    "avg_score_change": (this_week.get("avg_total_score") or 0) - (last_week.get("avg_total_score") or 0),
                }

        return {
            "trends": trends,
            "comparison": comparison if comparison else None,
            "non_rag_stats": {
                "direct_injection_count": non_rag_direct,
                "selected_documents_count": non_rag_selected,
                "non_rag_ratio": (non_rag_direct + non_rag_selected) / total_all if total_all > 0 else 0,
            },
        }

    async def compare_periods(
        self,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
        knowledge_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compare evaluation statistics between two time periods."""

        async def get_period_stats(start: date, end: date) -> Dict[str, Any]:
            conditions = [
                RagRecordRef.record_date >= start,
                RagRecordRef.record_date <= end,
                RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value,
                RagRecordRef.evaluation_status == RagRecordEvaluationStatus.COMPLETED.value,
            ]
            if knowledge_id:
                conditions.append(RagRecordRef.knowledge_id == knowledge_id)

            result = await self.db.execute(
                select(
                    func.count(EvaluationResult.id).label("count"),
                    func.sum(case((EvaluationResult.evaluation_judgment == "pass", 1), else_=0)).label("pass_count"),
                    func.avg(EvaluationResult.total_score).label("avg_score"),
                )
                .join(RagRecordRef, RagRecordRef.evaluation_result_id == EvaluationResult.id)
                .where(and_(*conditions))
            )
            row = result.fetchone()

            count = int(row.count or 0) if row else 0
            pass_count = int(row.pass_count or 0) if row else 0

            return {
                "date_range": f"{start.isoformat()} ~ {end.isoformat()}",
                "evaluated_count": count,
                "pass_rate": pass_count / count if count > 0 else None,
                "avg_total_score": float(row.avg_score) if row and row.avg_score else None,
            }

        period1 = await get_period_stats(period1_start, period1_end)
        period2 = await get_period_stats(period2_start, period2_end)

        pass_rate_change = None
        avg_score_change = None
        improvement = False

        if period1["pass_rate"] is not None and period2["pass_rate"] is not None:
            pass_rate_change = period2["pass_rate"] - period1["pass_rate"]
            improvement = pass_rate_change > 0

        if period1["avg_total_score"] is not None and period2["avg_total_score"] is not None:
            avg_score_change = period2["avg_total_score"] - period1["avg_total_score"]
            if not improvement and avg_score_change and avg_score_change > 0:
                improvement = True

        return {
            "period1": period1,
            "period2": period2,
            "changes": {
                "pass_rate_change": pass_rate_change,
                "avg_score_change": avg_score_change,
                "improvement": improvement,
            },
        }

    async def get_low_score_queries(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        knowledge_id: Optional[int] = None,
        judgment: str = "all",
        sort_by: str = "total_score",
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
        """Get low-score queries ranking."""
        conditions = [
            RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value,
            RagRecordRef.evaluation_status == RagRecordEvaluationStatus.COMPLETED.value,
        ]

        if start_date:
            conditions.append(RagRecordRef.record_date >= start_date)
        if end_date:
            conditions.append(RagRecordRef.record_date <= end_date)
        if knowledge_id:
            conditions.append(RagRecordRef.knowledge_id == knowledge_id)
        if judgment == "fail":
            conditions.append(EvaluationResult.evaluation_judgment == "fail")

        # Count total
        count_query = (
            select(func.count(RagRecordRef.id))
            .join(EvaluationResult, RagRecordRef.evaluation_result_id == EvaluationResult.id)
            .where(and_(*conditions))
        )
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Sort mapping
        sort_map = {
            "total_score": EvaluationResult.total_score,
            "faithfulness_score": EvaluationResult.faithfulness_score,
            "trulens_groundedness": EvaluationResult.trulens_groundedness,
            "ragas_query_context_relevance": EvaluationResult.ragas_query_context_relevance,
            "trulens_context_relevance": EvaluationResult.trulens_context_relevance,
        }
        order_column = sort_map.get(sort_by, EvaluationResult.total_score)

        # Fetch records
        query = (
            select(RagRecordRef, EvaluationResult)
            .join(EvaluationResult, RagRecordRef.evaluation_result_id == EvaluationResult.id)
            .where(and_(*conditions))
            .order_by(order_column.asc().nulls_last())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        rows = result.all()

        # Fetch raw data for user prompts
        raw_ids = [r[0].raw_id for r in rows]
        raw_details = await self.raw_tm.fetch_subtask_context_details(raw_ids) if raw_ids else {}

        # Fetch KB metadata
        kb_ids = list({r[0].knowledge_id for r in rows if r[0].knowledge_id})
        kb_metas = await self.raw_tm.fetch_kb_metas(kb_ids) if kb_ids else {}

        records = []
        for rag_ref, eval_result in rows:
            raw_detail = raw_details.get(rag_ref.raw_id, {})
            type_data = raw_detail.get("type_data", {})
            rag_result = type_data.get("rag_result", {})
            kb_meta = kb_metas.get(rag_ref.knowledge_id, {}) if rag_ref.knowledge_id else {}

            records.append({
                "rag_record_ref_id": rag_ref.id,
                "raw_id": rag_ref.raw_id,
                "record_date": rag_ref.record_date.isoformat() if rag_ref.record_date else None,
                "knowledge_id": rag_ref.knowledge_id,
                "knowledge_name": kb_meta.get("knowledge_name"),
                "user_prompt": rag_result.get("query"),
                "evaluation_judgment": eval_result.evaluation_judgment,
                "total_score": eval_result.total_score,
                "faithfulness_score": eval_result.faithfulness_score,
                "trulens_groundedness": eval_result.trulens_groundedness,
                "ragas_query_context_relevance": eval_result.ragas_query_context_relevance,
                "trulens_context_relevance": eval_result.trulens_context_relevance,
                "evaluated_at": rag_ref.evaluated_at,
            })

        filters_applied = {
            "date_range": f"{start_date.isoformat() if start_date else 'N/A'} ~ {end_date.isoformat() if end_date else 'N/A'}",
            "knowledge_id": knowledge_id,
            "judgment": judgment,
            "sort_by": sort_by,
        }

        return records, total, filters_applied

    async def get_low_score_knowledge_bases(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        judgment: str = "all",
        sort_by: str = "avg_total_score",
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get low-score knowledge bases ranking."""
        conditions = [
            RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value,
            RagRecordRef.evaluation_status == RagRecordEvaluationStatus.COMPLETED.value,
            RagRecordRef.knowledge_id.isnot(None),
        ]

        if start_date:
            conditions.append(RagRecordRef.record_date >= start_date)
        if end_date:
            conditions.append(RagRecordRef.record_date <= end_date)

        # Group by knowledge_id
        query = (
            select(
                RagRecordRef.knowledge_id,
                func.count(EvaluationResult.id).label("evaluated_count"),
                func.sum(case((EvaluationResult.evaluation_judgment == "pass", 1), else_=0)).label("pass_count"),
                func.sum(case((EvaluationResult.evaluation_judgment == "fail", 1), else_=0)).label("fail_count"),
                func.sum(case((EvaluationResult.evaluation_judgment == "undetermined", 1), else_=0)).label("undetermined_count"),
                func.avg(EvaluationResult.total_score).label("avg_total_score"),
                func.avg(EvaluationResult.faithfulness_score).label("avg_faithfulness_score"),
                func.avg(EvaluationResult.trulens_groundedness).label("avg_trulens_groundedness"),
                func.avg(EvaluationResult.ragas_query_context_relevance).label("avg_ragas_query_context_relevance"),
                func.avg(EvaluationResult.trulens_context_relevance).label("avg_trulens_context_relevance"),
            )
            .join(EvaluationResult, RagRecordRef.evaluation_result_id == EvaluationResult.id)
            .where(and_(*conditions))
            .group_by(RagRecordRef.knowledge_id)
        )

        # Count total KBs
        count_subquery = query.subquery()
        count_result = await self.db.execute(select(func.count()).select_from(count_subquery))
        total = count_result.scalar() or 0

        # Sort mapping
        sort_map = {
            "avg_total_score": func.avg(EvaluationResult.total_score),
            "avg_faithfulness": func.avg(EvaluationResult.faithfulness_score),
            "avg_groundedness": func.avg(EvaluationResult.trulens_groundedness),
            "avg_query_context_relevance": func.avg(EvaluationResult.ragas_query_context_relevance),
            "avg_context_relevance": func.avg(EvaluationResult.trulens_context_relevance),
            "fail_rate": func.sum(case((EvaluationResult.evaluation_judgment == "fail", 1), else_=0)) / func.count(EvaluationResult.id),
        }
        order_expr = sort_map.get(sort_by, func.avg(EvaluationResult.total_score))

        query = query.order_by(order_expr.asc().nulls_last()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        # Fetch KB metadata
        kb_ids = [r.knowledge_id for r in rows if r.knowledge_id]
        kb_metas = await self.raw_tm.fetch_kb_metas(kb_ids) if kb_ids else {}

        knowledge_bases = []
        for row in rows:
            kb_meta = kb_metas.get(row.knowledge_id, {}) if row.knowledge_id else {}
            evaluated_count = int(row.evaluated_count or 0)
            pass_count = int(row.pass_count or 0)
            fail_count = int(row.fail_count or 0)

            knowledge_bases.append({
                "knowledge_id": row.knowledge_id,
                "knowledge_name": kb_meta.get("knowledge_name"),
                "namespace": kb_meta.get("namespace"),
                "evaluated_count": evaluated_count,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "undetermined_count": int(row.undetermined_count or 0),
                "pass_rate": pass_count / evaluated_count if evaluated_count > 0 else None,
                "fail_rate": fail_count / evaluated_count if evaluated_count > 0 else None,
                "avg_total_score": float(row.avg_total_score) if row.avg_total_score else None,
                "avg_faithfulness_score": float(row.avg_faithfulness_score) if row.avg_faithfulness_score else None,
                "avg_trulens_groundedness": float(row.avg_trulens_groundedness) if row.avg_trulens_groundedness else None,
                "avg_ragas_query_context_relevance": float(row.avg_ragas_query_context_relevance) if row.avg_ragas_query_context_relevance else None,
                "avg_trulens_context_relevance": float(row.avg_trulens_context_relevance) if row.avg_trulens_context_relevance else None,
            })

        return knowledge_bases, total

    async def get_rag_record_evaluation_detail(
        self, rag_record_ref_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get evaluation detail for a single RAG record."""
        result = await self.db.execute(
            select(RagRecordRef).where(RagRecordRef.id == rag_record_ref_id)
        )
        rag_ref = result.scalar_one_or_none()

        if not rag_ref:
            return None

        # Get evaluation result
        eval_result = None
        if rag_ref.evaluation_result_id:
            eval_query = await self.db.execute(
                select(EvaluationResult).where(EvaluationResult.id == rag_ref.evaluation_result_id)
            )
            eval_result = eval_query.scalar_one_or_none()

        # Get raw data
        raw_details = await self.raw_tm.fetch_subtask_context_details([rag_ref.raw_id])
        raw_detail = raw_details.get(rag_ref.raw_id, {})
        type_data = raw_detail.get("type_data", {})
        rag_result = type_data.get("rag_result", {})
        chunks = rag_result.get("chunks", [])

        return {
            "rag_record_ref_id": rag_ref.id,
            "raw_id": rag_ref.raw_id,
            "evaluation_status": rag_ref.evaluation_status,
            "evaluation_result": {
                "id": eval_result.id,
                "evaluation_judgment": eval_result.evaluation_judgment,
                "total_score": eval_result.total_score,
                "retrieval_score": eval_result.retrieval_score,
                "generation_score": eval_result.generation_score,
                "core_metrics": {
                    "faithfulness_score": eval_result.faithfulness_score,
                    "trulens_groundedness": eval_result.trulens_groundedness,
                    "ragas_query_context_relevance": eval_result.ragas_query_context_relevance,
                    "trulens_context_relevance": eval_result.trulens_context_relevance,
                    "ragas_context_precision_emb": eval_result.ragas_context_precision_emb,
                },
                "threshold": getattr(settings, "EVALUATION_CORE_THRESHOLD", 0.6),
                "evaluated_at": rag_ref.evaluated_at,
            } if eval_result else None,
            "raw_data": {
                "user_prompt": rag_result.get("query"),
                "chunks_count": len(chunks),
                "chunks_preview": [c.get("text", "")[:200] + "..." for c in chunks[:5]] if chunks else None,
            },
        }

    async def get_kb_evaluation_stats(
        self, knowledge_id: int
    ) -> Dict[str, Any]:
        """Get evaluation statistics for a knowledge base."""
        conditions = [
            RagRecordRef.knowledge_id == knowledge_id,
            RagRecordRef.injection_mode == InjectionMode.RAG_RETRIEVAL.value,
        ]

        # Count RAG retrieval records
        rag_count_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(and_(*conditions))
        )
        rag_retrieval_count = rag_count_result.scalar() or 0

        # Count evaluated records
        evaluated_conditions = conditions + [
            RagRecordRef.evaluation_status == RagRecordEvaluationStatus.COMPLETED.value
        ]
        evaluated_result = await self.db.execute(
            select(func.count(RagRecordRef.id)).where(and_(*evaluated_conditions))
        )
        evaluated_count = evaluated_result.scalar() or 0

        # Get evaluation stats
        eval_query = (
            select(
                func.sum(case((EvaluationResult.evaluation_judgment == "pass", 1), else_=0)).label("pass_count"),
                func.sum(case((EvaluationResult.evaluation_judgment == "fail", 1), else_=0)).label("fail_count"),
                func.sum(case((EvaluationResult.evaluation_judgment == "undetermined", 1), else_=0)).label("undetermined_count"),
                func.avg(EvaluationResult.total_score).label("avg_total_score"),
            )
            .join(RagRecordRef, RagRecordRef.evaluation_result_id == EvaluationResult.id)
            .where(and_(*evaluated_conditions))
        )
        eval_result = await self.db.execute(eval_query)
        eval_row = eval_result.fetchone()

        pass_count = int(eval_row.pass_count or 0) if eval_row else 0
        fail_count = int(eval_row.fail_count or 0) if eval_row else 0
        undetermined_count = int(eval_row.undetermined_count or 0) if eval_row else 0

        return {
            "rag_retrieval_count": rag_retrieval_count,
            "evaluated_count": evaluated_count,
            "evaluation_coverage": evaluated_count / rag_retrieval_count if rag_retrieval_count > 0 else 0,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "undetermined_count": undetermined_count,
            "pass_rate": pass_count / evaluated_count if evaluated_count > 0 else None,
            "avg_total_score": float(eval_row.avg_total_score) if eval_row and eval_row.avg_total_score else None,
        }
