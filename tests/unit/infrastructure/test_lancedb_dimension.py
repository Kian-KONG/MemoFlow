"""LanceDB 向量维度校验：切换 Embedding 模型/维度时给出明确错误。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memoflow.domain.knowledge.entities import KnowledgeChunk
from memoflow.domain.knowledge.value_objects import Embedding
from memoflow.infrastructure.vectorstore.lancedb_repository import (
    LanceDBVectorRepository,
    _table_vector_dimension,
)


def _chunk_with_dim(meeting_id: str, dim: int) -> KnowledgeChunk:
    chunk = KnowledgeChunk.create(
        meeting_id=meeting_id,
        text="hello",
        source_utterance_ids=["u1"],
    )
    chunk.attach_embedding(Embedding.from_list([0.1] * dim))
    return chunk


def test_table_vector_dimension_reads_fixed_list_size() -> None:
    field_type = MagicMock()
    field_type.list_size = 1536
    field = MagicMock()
    field.type = field_type
    table = MagicMock()
    table.schema.field.return_value = field

    assert _table_vector_dimension(table) == 1536
    table.schema.field.assert_called_once_with("vector")


def test_upsert_rejects_dimension_mismatch(tmp_path: Path) -> None:
    repo = LanceDBVectorRepository(str(tmp_path / "lancedb"))
    repo._upsert_sync([_chunk_with_dim("m1", 3)])

    with pytest.raises(ValueError, match="向量维度不匹配"):
        repo._upsert_sync([_chunk_with_dim("m1", 4)])


def test_search_rejects_dimension_mismatch(tmp_path: Path) -> None:
    repo = LanceDBVectorRepository(str(tmp_path / "lancedb"))
    repo._upsert_sync([_chunk_with_dim("m1", 3)])

    with pytest.raises(ValueError, match="向量维度不匹配"):
        repo._search_sync(Embedding.from_list([0.2] * 8), top_k=3, meeting_id=None)


def test_matching_dimension_allows_upsert_and_search(tmp_path: Path) -> None:
    repo = LanceDBVectorRepository(str(tmp_path / "lancedb"))
    repo._upsert_sync([_chunk_with_dim("m1", 4)])
    hits = repo._search_sync(Embedding.from_list([0.1] * 4), top_k=3, meeting_id="m1")
    assert len(hits) == 1
    assert hits[0].meeting_id == "m1"
