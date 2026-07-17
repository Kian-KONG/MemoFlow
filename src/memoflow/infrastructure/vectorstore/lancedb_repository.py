"""VectorRepository 的 LanceDB 实现（本地嵌入式向量数据库，无需单独部署服务）。

LanceDB 的 Python SDK 是同步的，这里通过 `asyncio.to_thread` 包装为异步接口，
避免阻塞事件循环，同时对上层（应用层）保持异步契约一致。
"""
from __future__ import annotations

import asyncio
import json

import lancedb
import pyarrow as pa

from memoflow.domain.knowledge.entities import KnowledgeChunk
from memoflow.domain.knowledge.repository import KnowledgeSearchHit, VectorRepository
from memoflow.domain.knowledge.value_objects import Embedding

_TABLE_NAME = "knowledge_chunks"
_VECTOR_COLUMN = "vector"


def _escape_literal(value: str) -> str:
    """转义用于 LanceDB SQL 过滤表达式中的字符串字面量，防止过滤条件注入。"""
    return value.replace("'", "''")


def _table_vector_dimension(table: lancedb.table.Table) -> int | None:
    """从已有表的 schema 读取固定长度 vector 列维度；无法识别时返回 None。"""
    field = table.schema.field(_VECTOR_COLUMN)
    list_size = getattr(field.type, "list_size", None)
    if isinstance(list_size, int) and list_size > 0:
        return list_size
    return None


class LanceDBVectorRepository(VectorRepository):
    def __init__(self, db_uri: str) -> None:
        self._db_uri = db_uri
        self._db: lancedb.DBConnection | None = None

    def _connect(self) -> lancedb.DBConnection:
        if self._db is None:
            self._db = lancedb.connect(self._db_uri)
        return self._db

    def _dimension_mismatch_error(self, stored_dim: int, expected_dim: int) -> ValueError:
        return ValueError(
            f"LanceDB 向量维度不匹配：表中已有维度为 {stored_dim}，"
            f"当前 Embedding 维度为 {expected_dim}。"
            f"更换 Embedding 模型或维度后需清空并重建向量库目录 "
            f"（当前路径：{self._db_uri}，默认一般为 data/lancedb）。"
        )

    def _ensure_compatible_dimension(self, table: lancedb.table.Table, expected_dim: int) -> None:
        stored_dim = _table_vector_dimension(table)
        if stored_dim is None:
            return
        if stored_dim != expected_dim:
            raise self._dimension_mismatch_error(stored_dim, expected_dim)

    def _open_table_or_none(self) -> lancedb.table.Table | None:
        """尝试打开知识库表，不存在时返回 None。

        注意：不同版本的 LanceDB，`list_tables()` / `table_names()` 返回类型不尽相同
        （新版本返回分页的响应对象而非纯列表），直接做成员判断容易产生误判，
        因此这里改为直接尝试打开表、按异常判断是否存在，兼容性更好。
        """
        db = self._connect()
        try:
            return db.open_table(_TABLE_NAME)
        except (ValueError, FileNotFoundError):
            return None

    def _get_or_create_table(self, dim: int) -> lancedb.table.Table:
        existing = self._open_table_or_none()
        if existing is not None:
            self._ensure_compatible_dimension(existing, dim)
            return existing
        db = self._connect()
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("meeting_id", pa.string()),
                pa.field("text", pa.string()),
                pa.field("source_utterance_ids", pa.string()),  # JSON 编码的字符串数组
                pa.field(_VECTOR_COLUMN, pa.list_(pa.float32(), dim)),
            ]
        )
        return db.create_table(_TABLE_NAME, schema=schema)

    async def upsert(self, chunks: list[KnowledgeChunk]) -> None:
        await asyncio.to_thread(self._upsert_sync, chunks)

    def _upsert_sync(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        embedded = [c for c in chunks if c.embedding is not None]
        if not embedded:
            return
        dim = embedded[0].embedding.dimension  # type: ignore[union-attr]
        table = self._get_or_create_table(dim)
        records = [
            {
                "id": str(chunk.id),
                "meeting_id": chunk.meeting_id,
                "text": chunk.text,
                "source_utterance_ids": json.dumps(chunk.source_utterance_ids),
                "vector": list(chunk.embedding.vector),  # type: ignore[union-attr]
            }
            for chunk in embedded
        ]
        table.add(records)

    async def search(
        self,
        query_embedding: Embedding,
        top_k: int = 5,
        meeting_id: str | None = None,
    ) -> list[KnowledgeSearchHit]:
        return await asyncio.to_thread(self._search_sync, query_embedding, top_k, meeting_id)

    def _search_sync(
        self, query_embedding: Embedding, top_k: int, meeting_id: str | None
    ) -> list[KnowledgeSearchHit]:
        table = self._open_table_or_none()
        if table is None:
            return []
        self._ensure_compatible_dimension(table, query_embedding.dimension)
        query = table.search(list(query_embedding.vector)).limit(top_k)
        if meeting_id:
            query = query.where(f"meeting_id = '{_escape_literal(meeting_id)}'")

        hits: list[KnowledgeSearchHit] = []
        for row in query.to_list():
            distance = row.get("_distance", 0.0)
            hits.append(
                KnowledgeSearchHit(
                    chunk_id=row["id"],
                    meeting_id=row["meeting_id"],
                    text=row["text"],
                    score=1.0 / (1.0 + distance),  # 距离越小得分越高，归一化到 (0, 1]
                    source_utterance_ids=json.loads(row["source_utterance_ids"]),
                    metadata={},
                )
            )
        return hits

    async def delete_by_meeting(self, meeting_id: str) -> None:
        await asyncio.to_thread(self._delete_by_meeting_sync, meeting_id)

    def _delete_by_meeting_sync(self, meeting_id: str) -> None:
        table = self._open_table_or_none()
        if table is None:
            return
        table.delete(f"meeting_id = '{_escape_literal(meeting_id)}'")
