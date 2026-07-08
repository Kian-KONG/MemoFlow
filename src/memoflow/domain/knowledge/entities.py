"""知识库（Knowledge）聚合根：KnowledgeChunk。

每个 KnowledgeChunk 是转写文本按说话轮次 / 长度切分后的一个可检索片段，
携带来源会议、来源话语引用及向量表示，用于 RAG 检索。
"""
from __future__ import annotations

from datetime import datetime

from memoflow.domain.knowledge.value_objects import ChunkId, Embedding
from memoflow.domain.shared.entity import AggregateRoot, utcnow
from memoflow.domain.shared.exceptions import InvariantViolationError


class KnowledgeChunk(AggregateRoot[ChunkId]):
    def __init__(
        self,
        chunk_id: ChunkId,
        meeting_id: str,
        text: str,
        source_utterance_ids: list[str],
        created_at: datetime,
        embedding: Embedding | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        super().__init__(chunk_id)
        if not text.strip():
            raise InvariantViolationError("知识片段文本不能为空")
        self.meeting_id = meeting_id
        self.text = text
        self.source_utterance_ids = source_utterance_ids
        self.created_at = created_at
        self.embedding = embedding
        self.metadata = metadata or {}

    @classmethod
    def create(
        cls,
        meeting_id: str,
        text: str,
        source_utterance_ids: list[str],
        metadata: dict[str, str] | None = None,
    ) -> "KnowledgeChunk":
        return cls(
            chunk_id=ChunkId.new(),
            meeting_id=meeting_id,
            text=text,
            source_utterance_ids=source_utterance_ids,
            created_at=utcnow(),
            metadata=metadata,
        )

    def attach_embedding(self, embedding: Embedding) -> None:
        self.embedding = embedding
