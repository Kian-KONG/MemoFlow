"""摘要（Summary）仓储端口。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from memoflow.domain.summary.entities import Summary
from memoflow.domain.summary.value_objects import SummaryId


class SummaryRepository(ABC):
    @abstractmethod
    async def add(self, summary: Summary) -> None: ...

    @abstractmethod
    async def get(self, summary_id: SummaryId) -> Summary | None: ...

    @abstractmethod
    async def get_by_meeting_id(self, meeting_id: str) -> Summary | None: ...

    @abstractmethod
    async def save(self, summary: Summary) -> None: ...
