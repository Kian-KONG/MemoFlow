"""TranscriptRepository 的 SQLAlchemy 实现。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memoflow.domain.transcript.entities import Transcript
from memoflow.domain.transcript.repository import TranscriptRepository
from memoflow.domain.transcript.value_objects import TranscriptId
from memoflow.infrastructure.persistence.mappers import transcript_to_domain, transcript_to_model
from memoflow.infrastructure.persistence.models import TranscriptModel


class SqlAlchemyTranscriptRepository(TranscriptRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transcript: Transcript) -> None:
        self._session.add(transcript_to_model(transcript))

    async def get(self, transcript_id: TranscriptId) -> Transcript | None:
        model = await self._session.get(TranscriptModel, str(transcript_id))
        return transcript_to_domain(model) if model else None

    async def get_by_meeting_id(self, meeting_id: str) -> Transcript | None:
        stmt = select(TranscriptModel).where(TranscriptModel.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return transcript_to_domain(model) if model else None

    async def save(self, transcript: Transcript) -> None:
        model = await self._session.get(TranscriptModel, str(transcript.id))
        if model is None:
            self._session.add(transcript_to_model(transcript))
            return
        # 说话人重命名 / 说话人分配等更新场景：整体替换子集合（简单可靠，转写数据量不大）
        await self._session.delete(model)
        await self._session.flush()
        self._session.add(transcript_to_model(transcript))

    async def delete_by_meeting_id(self, meeting_id: str) -> None:
        stmt = select(TranscriptModel).where(TranscriptModel.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._session.delete(model)
