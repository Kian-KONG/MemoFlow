"""知识库（Knowledge）向量仓储端口（Port）。

具体实现位于 `memoflow.infrastructure.vectorstore.lancedb_repository`，
若未来需要替换为 Chroma / Qdrant / pgvector，只需实现本接口即可。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from memoflow.domain.knowledge.entities import KnowledgeChunk
from memoflow.domain.knowledge.value_objects import Embedding


@dataclass(frozen=True)
class KnowledgeSearchHit:
    """一次向量检索命中的结果。"""

    chunk_id: str
    meeting_id: str
    text: str
    score: float
    source_utterance_ids: list[str]
    metadata: dict[str, str]


class VectorRepository(ABC):
    @abstractmethod
    async def upsert(self, chunks: list[KnowledgeChunk]) -> None: ...

    @abstractmethod
    async def search(
        self,
        query_embedding: Embedding,
        top_k: int = 5,
        meeting_id: str | None = None,
    ) -> list[KnowledgeSearchHit]: ...

    @abstractmethod
    async def delete_by_meeting(self, meeting_id: str) -> None: ...
