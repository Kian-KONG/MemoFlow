"""基于 SQLAlchemy AsyncSession 的工作单元实现。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from memoflow.application.ports.unit_of_work import UnitOfWork
from memoflow.infrastructure.persistence.meeting_repository_impl import SqlAlchemyMeetingRepository
from memoflow.infrastructure.persistence.summary_repository_impl import SqlAlchemySummaryRepository
from memoflow.infrastructure.persistence.transcript_repository_impl import (
    SqlAlchemyTranscriptRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._session_factory()
        self.meetings = SqlAlchemyMeetingRepository(self._session)
        self.transcripts = SqlAlchemyTranscriptRepository(self._session)
        self.summaries = SqlAlchemySummaryRepository(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        assert self._session is not None
        try:
            if exc is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
