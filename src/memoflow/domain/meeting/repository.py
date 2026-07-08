"""会议（Meeting）仓储端口（Port）。

领域层只定义抽象接口，具体实现（SQLite/SQLAlchemy）位于
`memoflow.infrastructure.persistence`，符合依赖倒置原则，
方便未来替换为 PostgreSQL 等其他存储而不影响领域 / 应用层。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.value_objects import MeetingId, MeetingStatus


class MeetingRepository(ABC):
    @abstractmethod
    async def add(self, meeting: Meeting) -> None: ...

    @abstractmethod
    async def get(self, meeting_id: MeetingId) -> Meeting | None: ...

    @abstractmethod
    async def list_all(
        self, status: MeetingStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Meeting]: ...

    @abstractmethod
    async def save(self, meeting: Meeting) -> None:
        """持久化聚合根的当前状态（新增或更新）。"""

    @abstractmethod
    async def delete(self, meeting_id: MeetingId) -> None: ...
