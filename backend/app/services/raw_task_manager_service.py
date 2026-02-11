"""Raw task_manager DB access service.

This module centralizes reads from the Raw DB (task_manager), such as:
- kinds (KnowledgeBase)
- users
- subtask_contexts

Rationale: avoid scattering raw DB SQL across feature services.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.raw_database import get_raw_session_factory, is_raw_db_configured

logger = structlog.get_logger(__name__)


class RawTaskManagerService:
    """Encapsulates read-only queries to task_manager (Raw DB)."""

    def __init__(self, db: Optional[AsyncSession] = None):
        # Keep signature flexible for callers that already have a local db session.
        # Raw DB access does not use this session; it uses the raw session factory.
        self.db = db

    async def fetch_user_names(self, user_ids: List[int]) -> Dict[int, str]:
        """Fetch user_name mapping from task_manager.users."""
        if not user_ids or not is_raw_db_configured():
            return {}

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return {}

        unique_ids = sorted({int(x) for x in user_ids if x is not None})
        if not unique_ids:
            return {}

        async with session_factory() as raw_session:
            query = text(
                """
                SELECT id, user_name
                FROM users
                WHERE id IN :user_ids
                """
            )
            result = await raw_session.execute(query, {"user_ids": tuple(unique_ids)})
            return {row.id: row.user_name for row in result.fetchall()}

    async def fetch_kb_metas(self, kb_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch KB meta from task_manager.kinds for KnowledgeBase entries.

        Returns a mapping:
          kb_id -> {
            knowledge_name,
            namespace,
            created_by_user_id,
          }

        Notes:
        - knowledge_name is derived from kinds.json.spec.name (fallback to kinds.name)
        - namespace is derived from kinds.json.metadata.namespace (fallback to kinds.namespace)
        """
        if not kb_ids or not is_raw_db_configured():
            return {}

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return {}

        unique_ids = sorted({int(x) for x in kb_ids if x is not None})
        if not unique_ids:
            return {}

        async with session_factory() as raw_session:
            query = text(
                """
                SELECT id, user_id, name, namespace, json
                FROM kinds
                WHERE kind = 'KnowledgeBase'
                  AND id IN :kb_ids
                """
            )
            result = await raw_session.execute(query, {"kb_ids": tuple(unique_ids)})

            metas: Dict[int, Dict[str, Any]] = {}
            for row in result.fetchall():
                import json as json_module

                kb_json = row.json
                if isinstance(kb_json, str):
                    kb_json = json_module.loads(kb_json)

                spec = (kb_json or {}).get("spec", {})
                metadata = (kb_json or {}).get("metadata", {})

                display_name = spec.get("name", row.name)
                namespace = metadata.get("namespace", row.namespace)

                metas[int(row.id)] = {
                    "knowledge_name": display_name,
                    "namespace": namespace,
                    "created_by_user_id": int(row.user_id) if row.user_id is not None else None,
                }

            return metas

    async def list_knowledge_bases(
        self,
        limit: int = 20,
        offset: int = 0,
        q: Optional[str] = None,
        sort_by: str = "id",
    ) -> tuple[List[Dict[str, Any]], int]:
        """List KnowledgeBase items from task_manager.kinds with optional search.

        Search behavior:
        - If q is digits: match kb id OR creator user_id
        - Else: fuzzy match on kinds.name / kinds.namespace / kinds.json / users.user_name (string contains)

        sort_by:
        - 'id' (default): id desc
        - 'name': name asc
        - 'created_by': user_id desc
        """
        if not is_raw_db_configured():
            return [], 0

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return [], 0

        q = (q or "").strip() or None

        # Build WHERE
        where_sql = "WHERE k.kind = 'KnowledgeBase'"
        params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

        if q:
            if q.isdigit():
                q_int = int(q)
                where_sql += " AND (k.id = :q_int OR k.user_id = :q_int)"
                params["q_int"] = q_int
            else:
                like = f"%{q}%"
                where_sql += (
                    " AND (k.name LIKE :q_like OR k.namespace LIKE :q_like OR k.json LIKE :q_like OR u.user_name LIKE :q_like)"
                )
                params["q_like"] = like

        # ORDER BY
        if sort_by == "name":
            order_sql = "ORDER BY k.name ASC, k.id DESC"
        elif sort_by == "created_by":
            order_sql = "ORDER BY k.user_id DESC, k.id DESC"
        else:
            order_sql = "ORDER BY k.id DESC"

        async with session_factory() as raw_session:
            count_query = text(
                f"""
                SELECT COUNT(1) AS total
                FROM kinds k
                LEFT JOIN users u ON u.id = k.user_id
                {where_sql}
                """
            )
            count_res = await raw_session.execute(count_query, params)
            row = count_res.fetchone()
            total = int(row.total) if row and getattr(row, "total", None) is not None else 0

            data_query = text(
                f"""
                SELECT k.id,
                       k.user_id,
                       u.user_name,
                       k.name,
                       k.namespace,
                       k.json,
                       k.created_at,
                       k.updated_at
                FROM kinds k
                LEFT JOIN users u ON u.id = k.user_id
                {where_sql}
                {order_sql}
                LIMIT :limit OFFSET :offset
                """
            )
            res = await raw_session.execute(data_query, params)

            items: List[Dict[str, Any]] = []
            for r in res.fetchall():
                import json as json_module

                kb_json = r.json
                if isinstance(kb_json, str):
                    kb_json = json_module.loads(kb_json)

                spec = (kb_json or {}).get("spec", {})
                metadata = (kb_json or {}).get("metadata", {})

                created_by_user_id = int(r.user_id) if r.user_id is not None else None

                # Best-effort description parsing from spec (field names may vary by version)
                raw_desc = (
                    spec.get("description")
                    or spec.get("desc")
                    or spec.get("summary")
                    or (metadata.get("annotations", {}) or {}).get("description")
                )

                description: Optional[str] = None
                if raw_desc is None:
                    description = None
                elif isinstance(raw_desc, str):
                    description = raw_desc
                elif isinstance(raw_desc, dict):
                    # Some KB store summary object; prefer short_summary/long_summary
                    description = (
                        raw_desc.get("short_summary")
                        or raw_desc.get("long_summary")
                        or raw_desc.get("summary")
                    )
                    if not isinstance(description, str):
                        description = None
                    if description is None:
                        # Fallback: stringify the object for display
                        description = json_module.dumps(raw_desc, ensure_ascii=False)
                elif isinstance(raw_desc, list):
                    description = "; ".join([str(x) for x in raw_desc if x is not None])
                else:
                    description = str(raw_desc)

                items.append(
                    {
                        "knowledge_id": int(r.id),
                        "knowledge_name": spec.get("name", r.name),
                        "namespace": metadata.get("namespace", r.namespace),
                        "created_by_user_id": created_by_user_id,
                        "created_by_user_name": r.user_name,
                        "description": description,
                        "kb_type": spec.get("kbType"),
                        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
                    }
                )

            return items, total

    async def fetch_subtask_context_details(self, raw_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Fetch subtask_contexts detail for a list of raw ids.

        Returns mapping raw_id -> {context_type, name, type_data, created_at}.
        """
        if not raw_ids or not is_raw_db_configured():
            return {}

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return {}

        unique_ids = sorted({int(x) for x in raw_ids if x is not None})
        if not unique_ids:
            return {}

        async with session_factory() as raw_session:
            query = text(
                """
                SELECT id, context_type, name, type_data, created_at
                FROM subtask_contexts
                WHERE id IN :raw_ids
                """
            )
            result = await raw_session.execute(query, {"raw_ids": tuple(unique_ids)})

            details: Dict[int, Dict[str, Any]] = {}
            for row in result.fetchall():
                import json as json_module

                type_data = row.type_data
                if isinstance(type_data, str):
                    type_data = json_module.loads(type_data)

                details[int(row.id)] = {
                    "context_type": row.context_type,
                    "name": row.name,
                    "type_data": type_data,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }

            return details

    async def fetch_extracted_text(self, raw_id: int) -> Optional[str]:
        """Fetch extracted_text for one subtask_context."""
        if not is_raw_db_configured():
            return None

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return None

        async with session_factory() as raw_session:
            query = text(
                """
                SELECT extracted_text
                FROM subtask_contexts
                WHERE id = :raw_id
                """
            )
            result = await raw_session.execute(query, {"raw_id": raw_id})
            row = result.fetchone()
            return row.extracted_text if row else None

    async def get_kb_detail(self, kb_id: int) -> Optional[Dict[str, Any]]:
        """Get KnowledgeBase detail (including creator info) by id."""
        if not is_raw_db_configured():
            return None

        session_factory = get_raw_session_factory()
        if session_factory is None:
            return None

        async with session_factory() as raw_session:
            query = text(
                """
                SELECT id, user_id, name, namespace, json, is_active, created_at, updated_at
                FROM kinds
                WHERE kind = 'KnowledgeBase' AND id = :kb_id
                """
            )
            result = await raw_session.execute(query, {"kb_id": kb_id})
            row = result.fetchone()
            if not row:
                return None

            import json as json_module

            kb_json = row.json
            if isinstance(kb_json, str):
                kb_json = json_module.loads(kb_json)

            spec = (kb_json or {}).get("spec", {})
            retrieval_config = spec.get("retrievalConfig", {})

            created_by_user_id = int(row.user_id) if row.user_id is not None else None
            user_names = await self.fetch_user_names([created_by_user_id] if created_by_user_id else [])

            return {
                "id": int(row.id),
                "name": spec.get("name", row.name),
                "namespace": row.namespace,
                "kb_type": spec.get("kbType"),
                "is_active": row.is_active,
                "created_by_user_id": created_by_user_id,
                "created_by_user_name": user_names.get(created_by_user_id) if created_by_user_id else None,
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
