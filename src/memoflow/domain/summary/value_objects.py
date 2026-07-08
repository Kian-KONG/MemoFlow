"""摘要（Summary）上下文 —— 值对象。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from memoflow.domain.shared.entity import ValueObject, new_uuid


@dataclass(frozen=True)
class SummaryId(ValueObject):
    value: str

    @staticmethod
    def new() -> "SummaryId":
        return SummaryId(new_uuid())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DecisionId(ValueObject):
    value: str

    @staticmethod
    def new() -> "DecisionId":
        return DecisionId(new_uuid())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ActionItemId(ValueObject):
    value: str

    @staticmethod
    def new() -> "ActionItemId":
        return ActionItemId(new_uuid())

    def __str__(self) -> str:
        return self.value


class ActionItemStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
