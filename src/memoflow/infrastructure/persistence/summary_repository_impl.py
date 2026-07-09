"""SummaryRepository 的 SQLAlchemy 实现。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memoflow.domain.summary.entities import Summary
from memoflow.domain.summary.repository import SummaryRepository
from memoflow.domain.summary.value_objects import SummaryId
from memoflow.infrastructure.persistence.mappers import summary_to_domain, summary_to_model
from memoflow.infrastructure.persistence.models import SummaryModel


class SqlAlchemySummaryRepository(SummaryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, summary: Summary) -> None:
        self._session.add(summary_to_model(summary))

    async def get(self, summary_id: SummaryId) -> Summary | None:
        model = await self._session.get(SummaryModel, str(summary_id))
        return summary_to_domain(model) if model else None

    async def get_by_meeting_id(self, meeting_id: str) -> Summary | None:
        stmt = select(SummaryModel).where(SummaryModel.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return summary_to_domain(model) if model else None

    async def save(self, summary: Summary) -> None:
        model = await self._session.get(SummaryModel, str(summary.id))
        if model is None:
            self._session.add(summary_to_model(summary))
            return
        await self._session.delete(model)
        await self._session.flush()
        self._session.add(summary_to_model(summary))

    async def delete_by_meeting_id(self, meeting_id: str) -> None:
        stmt = select(SummaryModel).where(SummaryModel.meeting_id == meeting_id)
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._session.delete(model)
