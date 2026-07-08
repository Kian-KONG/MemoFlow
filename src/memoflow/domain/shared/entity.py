"""Shared kernel: 领域层通用基类（Entity / AggregateRoot / ValueObject / DomainEvent）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

TId = TypeVar("TId")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ValueObject:
    """所有值对象的标记基类。值对象不可变、以属性值判等。"""


class DomainEvent:
    """领域事件基类。事件本身是不可变的事实描述。"""

    def __init__(self) -> None:
        self.occurred_at: datetime = utcnow()

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{self.__class__.__name__} occurred_at={self.occurred_at.isoformat()}>"


class Entity(Generic[TId]):
    """实体基类：以标识（id）判等，而非属性值。"""

    def __init__(self, entity_id: TId) -> None:
        self._id = entity_id

    @property
    def id(self) -> TId:
        return self._id

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self), self._id))


class AggregateRoot(Entity[TId]):
    """聚合根基类：负责维护聚合内部不变量，并收集待发布的领域事件。"""

    def __init__(self, entity_id: TId) -> None:
        super().__init__(entity_id)
        self._domain_events: list[DomainEvent] = []

    def record_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """取出并清空聚合内累积的领域事件，通常由应用层在事务提交后发布。"""
        events, self._domain_events = self._domain_events, []
        return events


def new_uuid() -> str:
    return str(uuid4())
