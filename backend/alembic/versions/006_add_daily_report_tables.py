"""Add daily report tables for RAG statistics

Revision ID: 006
Revises: 005
Create Date: 2026-02-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # 1. Create daily_stats table
    if not table_exists("daily_stats"):
        op.create_table(
            "daily_stats",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("date", sa.Date(), nullable=False, unique=True),
            sa.Column("total_queries", sa.Integer(), default=0, nullable=False),
            sa.Column("rag_retrieval_count", sa.Integer(), default=0, nullable=False),
            sa.Column("direct_injection_count", sa.Integer(), default=0, nullable=False),
            sa.Column("selected_documents_count", sa.Integer(), default=0, nullable=False),
            sa.Column("active_kb_count", sa.Integer(), default=0, nullable=False),
            sa.Column("active_user_count", sa.Integer(), default=0, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        op.create_index("ix_daily_stats_date", "daily_stats", ["date"])

    # 2. Create hourly_stats table
    if not table_exists("hourly_stats"):
        op.create_table(
            "hourly_stats",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("hour", sa.Integer(), nullable=False),
            sa.Column("total_queries", sa.Integer(), default=0, nullable=False),
            sa.Column("rag_retrieval_count", sa.Integer(), default=0, nullable=False),
            sa.Column("direct_injection_count", sa.Integer(), default=0, nullable=False),
            sa.Column("selected_documents_count", sa.Integer(), default=0, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("date", "hour", name="uq_hourly_stats_date_hour"),
        )
        op.create_index("ix_hourly_stats_date", "hourly_stats", ["date"])

    # 3. Create kb_daily_stats table
    if not table_exists("kb_daily_stats"):
        op.create_table(
            "kb_daily_stats",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("knowledge_id", sa.Integer(), nullable=False),
            sa.Column("knowledge_name", sa.String(255), nullable=True),
            sa.Column("namespace", sa.String(100), nullable=True),
            sa.Column("total_queries", sa.Integer(), default=0, nullable=False),
            sa.Column("rag_retrieval_count", sa.Integer(), default=0, nullable=False),
            sa.Column("direct_injection_count", sa.Integer(), default=0, nullable=False),
            sa.Column("selected_documents_count", sa.Integer(), default=0, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint("date", "knowledge_id", name="uq_kb_daily_stats_date_kb"),
        )
        op.create_index("ix_kb_daily_stats_date", "kb_daily_stats", ["date"])
        op.create_index("ix_kb_daily_stats_knowledge_id", "kb_daily_stats", ["knowledge_id"])

    # 4. Create rag_record_refs table
    if not table_exists("rag_record_refs"):
        op.create_table(
            "rag_record_refs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("raw_id", sa.Integer(), nullable=False, unique=True),
            sa.Column("knowledge_id", sa.Integer(), nullable=True),
            sa.Column("context_type", sa.String(50), nullable=True),
            sa.Column("injection_mode", sa.String(50), nullable=True),
            sa.Column("evaluation_status", sa.String(20), default="pending", nullable=False),
            sa.Column(
                "evaluation_result_id",
                sa.BigInteger(),
                sa.ForeignKey("evaluation_results.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("record_date", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_rag_record_refs_raw_id", "rag_record_refs", ["raw_id"])
        op.create_index("ix_rag_record_refs_knowledge_id", "rag_record_refs", ["knowledge_id"])
        op.create_index("ix_rag_record_refs_record_date", "rag_record_refs", ["record_date"])
        op.create_index("ix_rag_record_refs_evaluation_status", "rag_record_refs", ["evaluation_status"])
        op.create_index("ix_rag_record_refs_date_kb", "rag_record_refs", ["record_date", "knowledge_id"])

    # 5. Create sync_checkpoints table
    if not table_exists("sync_checkpoints"):
        op.create_table(
            "sync_checkpoints",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("sync_type", sa.String(20), nullable=False, unique=True),
            sa.Column("last_sync_time", sa.DateTime(), nullable=True),
            sa.Column("last_raw_id", sa.Integer(), default=0, nullable=False),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("error_message", sa.String(1000), nullable=True),
            sa.Column("records_synced", sa.Integer(), default=0, nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        )


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign key constraints)
    op.drop_table("sync_checkpoints")
    op.drop_table("rag_record_refs")
    op.drop_table("kb_daily_stats")
    op.drop_table("hourly_stats")
    op.drop_table("daily_stats")
