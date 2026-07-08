"""工作单元（Unit of Work）端口，用于跨聚合保证事务一致性。

具体实现：`memoflow.infrastructure.persistence.unit_of_work.SqlAlchemyUnitOfWork`。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Callable

from memoflow.domain.meeting.repository import MeetingRepository
from memoflow.domain.summary.repository import SummaryRepository
from memoflow.domain.transcript.repository import TranscriptRepository


class UnitOfWork(ABC):
    meetings: MeetingRepository
    transcripts: TranscriptRepository
    summaries: SummaryRepository

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            await self.rollback()
        else:
            pass  # 由调用方显式 commit，未 commit 的变更在退出时不会自动提交

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
