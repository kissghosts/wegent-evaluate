"""
Daily statistics models for RAG usage tracking.
"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class InjectionMode(str, enum.Enum):
    """RAG injection mode types."""

    RAG_RETRIEVAL = "rag_retrieval"
    DIRECT_INJECTION = "direct_injection"
    SELECTED_DOCUMENTS = "selected_documents"
    UNKNOWN = "unknown"


class RagRecordEvaluationStatus(str, enum.Enum):
    """Evaluation status for RAG records."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DailyStats(Base):
    """Daily aggregated statistics for RAG usage."""

    __tablename__ = "daily_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Query counts
    total_queries = Column(Integer, default=0, nullable=False)
    rag_retrieval_count = Column(Integer, default=0, nullable=False)
    direct_injection_count = Column(Integer, default=0, nullable=False)
    selected_documents_count = Column(Integer, default=0, nullable=False)

    # Active counts
    active_kb_count = Column(Integer, default=0, nullable=False)
    active_user_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<DailyStats(date={self.date}, total={self.total_queries})>"


class HourlyStats(Base):
    """Hourly statistics for RAG usage."""

    __tablename__ = "hourly_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    hour = Column(Integer, nullable=False)  # 0-23

    # Query counts
    total_queries = Column(Integer, default=0, nullable=False)
    rag_retrieval_count = Column(Integer, default=0, nullable=False)
    direct_injection_count = Column(Integer, default=0, nullable=False)
    selected_documents_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("date", "hour", name="uq_hourly_stats_date_hour"),
        Index("ix_hourly_stats_date", "date"),
    )

    def __repr__(self) -> str:
        return f"<HourlyStats(date={self.date}, hour={self.hour}, total={self.total_queries})>"


class KbDailyStats(Base):
    """Knowledge base daily statistics."""

    __tablename__ = "kb_daily_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    knowledge_id = Column(Integer, nullable=False)

    # Snapshot fields (cached from raw DB for display)
    knowledge_name = Column(String(255), nullable=True)
    namespace = Column(String(100), nullable=True)

    # Query counts
    total_queries = Column(Integer, default=0, nullable=False)
    rag_retrieval_count = Column(Integer, default=0, nullable=False)
    direct_injection_count = Column(Integer, default=0, nullable=False)
    selected_documents_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("date", "knowledge_id", name="uq_kb_daily_stats_date_kb"),
        Index("ix_kb_daily_stats_date", "date"),
        Index("ix_kb_daily_stats_knowledge_id", "knowledge_id"),
    )

    def __repr__(self) -> str:
        return f"<KbDailyStats(date={self.date}, kb_id={self.knowledge_id}, total={self.total_queries})>"


class RagRecordRef(Base):
    """Reference table for RAG records (links to raw DB subtask_contexts)."""

    __tablename__ = "rag_record_refs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Reference to raw DB (subtask_contexts.id)
    raw_id = Column(Integer, nullable=False, unique=True, index=True)

    # Cached fields for filtering (avoid querying raw DB for filters)
    knowledge_id = Column(Integer, nullable=True, index=True)
    context_type = Column(String(50), nullable=True)  # 'knowledge_base' | 'selected_documents'
    injection_mode = Column(String(50), nullable=True)  # 'rag_retrieval' | 'direct_injection' | null

    # Evaluation tracking
    evaluation_status = Column(
        String(20),
        default=RagRecordEvaluationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    evaluation_result_id = Column(
        BigInteger,
        ForeignKey("evaluation_results.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Date for quick filtering
    record_date = Column(Date, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to evaluation result
    evaluation_result = relationship("EvaluationResult", backref="rag_record_ref")

    __table_args__ = (
        Index("ix_rag_record_refs_date_kb", "record_date", "knowledge_id"),
        Index("ix_rag_record_refs_eval_status", "evaluation_status"),
    )

    def __repr__(self) -> str:
        return f"<RagRecordRef(id={self.id}, raw_id={self.raw_id}, kb_id={self.knowledge_id})>"


class SyncCheckpoint(Base):
    """Sync checkpoint for tracking incremental sync progress."""

    __tablename__ = "sync_checkpoints"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sync_type = Column(String(20), nullable=False, unique=True)  # 'hourly' | 'daily'

    # Sync progress
    last_sync_time = Column(DateTime, nullable=True)
    last_raw_id = Column(Integer, default=0, nullable=False)

    # Status tracking
    status = Column(String(20), nullable=True)  # 'success' | 'failed'
    error_message = Column(String(1000), nullable=True)
    records_synced = Column(Integer, default=0, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<SyncCheckpoint(type={self.sync_type}, last_id={self.last_raw_id})>"
