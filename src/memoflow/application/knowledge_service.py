"""知识库应用服务：将会议转写切分为片段、向量化并写入向量库；支持语义检索（RAG）。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.dto import KnowledgeHitDTO
from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.domain.knowledge.entities import KnowledgeChunk
from memoflow.domain.knowledge.repository import VectorRepository
from memoflow.domain.knowledge.value_objects import Embedding
from memoflow.domain.meeting.value_objects import MeetingId
from memoflow.domain.shared.exceptions import EntityNotFoundError
from memoflow.domain.transcript.entities import Transcript
from memoflow.domain.transcript.value_objects import TranscriptId

_DEFAULT_CHUNK_MAX_CHARS = 500


class KnowledgeApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        embedding: EmbeddingPort,
        vector_repository: VectorRepository,
        chunk_max_chars: int = _DEFAULT_CHUNK_MAX_CHARS,
    ) -> None:
        self._uow_factory = uow_factory
        self._embedding = embedding
        self._vector_repository = vector_repository
        self._chunk_max_chars = chunk_max_chars

    async def index_meeting(self, meeting_id: str) -> int:
        """将会议转写切分、向量化并写入知识库，返回索引的片段数量。"""
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            if meeting.transcript_id is None:
                raise EntityNotFoundError("Transcript", "(meeting has no transcript yet)")
            transcript = await uow.transcripts.get(TranscriptId(meeting.transcript_id))
            if transcript is None:
                raise EntityNotFoundError("Transcript", meeting.transcript_id)

        chunks_raw = self._chunk_transcript(transcript)
        if not chunks_raw:
            return 0

        texts = [text for text, _ in chunks_raw]
        vectors = await self._embedding.embed(texts)

        chunks: list[KnowledgeChunk] = []
        for (text, source_ids), vector in zip(chunks_raw, vectors, strict=True):
            chunk = KnowledgeChunk.create(
                meeting_id=meeting_id, text=text, source_utterance_ids=source_ids
            )
            chunk.attach_embedding(Embedding.from_list(vector))
            chunks.append(chunk)

        await self._vector_repository.upsert(chunks)
        logger.info(f"[{meeting_id}] 知识库索引完成，共 {len(chunks)} 个片段")
        return len(chunks)

    async def search(
        self, query: str, meeting_id: str | None = None, top_k: int = 5
    ) -> list[KnowledgeHitDTO]:
        """基于语义相似度检索相关的历史会议片段（RAG 检索入口）。"""
        query_vector = (await self._embedding.embed([query]))[0]
        hits = await self._vector_repository.search(
            query_embedding=Embedding.from_list(query_vector),
            top_k=top_k,
            meeting_id=meeting_id,
        )
        return [
            KnowledgeHitDTO(
                chunk_id=h.chunk_id,
                meeting_id=h.meeting_id,
                text=h.text,
                score=h.score,
                source_utterance_ids=h.source_utterance_ids,
            )
            for h in hits
        ]

    def _chunk_transcript(self, transcript: Transcript) -> list[tuple[str, list[str]]]:
        """按说话人轮次与最大字符数切分转写文本，保留来源话语 ID 以便追溯。"""
        chunks: list[tuple[str, list[str]]] = []
        buffer_text: list[str] = []
        buffer_ids: list[str] = []
        buffer_len = 0

        def flush() -> None:
            nonlocal buffer_text, buffer_ids, buffer_len
            if buffer_text:
                chunks.append(("\n".join(buffer_text), list(buffer_ids)))
            buffer_text, buffer_ids, buffer_len = [], [], 0

        for utterance in transcript.utterances:
            speaker_name = (
                transcript.speakers[utterance.speaker_id].name if utterance.speaker_id else "未知说话人"
            )
            line = f"[{speaker_name}] {utterance.text}"
            if buffer_len + len(line) > self._chunk_max_chars and buffer_text:
                flush()
            buffer_text.append(line)
            buffer_ids.append(str(utterance.id))
            buffer_len += len(line)

        flush()
        return chunks
