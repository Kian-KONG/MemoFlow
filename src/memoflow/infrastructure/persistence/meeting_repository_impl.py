"""MeetingRepository 的 SQLAlchemy 实现。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.repository import MeetingRepository
from memoflow.domain.meeting.value_objects import MeetingId, MeetingStatus
from memoflow.infrastructure.persistence.mappers import (
    apply_meeting_to_model,
    meeting_to_domain,
    meeting_to_model,
)
from memoflow.infrastructure.persistence.models import MeetingModel


class SqlAlchemyMeetingRepository(MeetingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, meeting: Meeting) -> None:
        self._session.add(meeting_to_model(meeting))

    async def get(self, meeting_id: MeetingId) -> Meeting | None:
        model = await self._session.get(MeetingModel, str(meeting_id))
        return meeting_to_domain(model) if model else None

    async def list_all(
        self, status: MeetingStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Meeting]:
        stmt = select(MeetingModel).order_by(MeetingModel.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(MeetingModel.status == status.value)
        result = await self._session.execute(stmt)
        return [meeting_to_domain(m) for m in result.scalars().all()]

    async def save(self, meeting: Meeting) -> None:
        model = await self._session.get(MeetingModel, str(meeting.id))
        if model is None:
            self._session.add(meeting_to_model(meeting))
        else:
            apply_meeting_to_model(meeting, model)

    async def delete(self, meeting_id: MeetingId) -> None:
        model = await self._session.get(MeetingModel, str(meeting_id))
        if model is not None:
            await self._session.delete(model)
