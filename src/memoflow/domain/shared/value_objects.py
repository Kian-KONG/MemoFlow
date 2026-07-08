"""共享值对象内核，供多个限界上下文复用（避免跨上下文直接依赖聚合内部实现）。"""
from __future__ import annotations

from dataclasses import dataclass

from memoflow.domain.shared.entity import ValueObject


@dataclass(frozen=True)
class TimeRange(ValueObject):
    """时间区间（秒），用于话语 / 说话人片段等场景。"""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("时间区间不能为负数")
        if self.end < self.start:
            raise ValueError("结束时间不能早于开始时间")

    @property
    def duration(self) -> float:
        return self.end - self.start

    def overlaps(self, other: "TimeRange") -> bool:
        return self.start < other.end and other.start < self.end

    def overlap_seconds(self, other: "TimeRange") -> float:
        return max(0.0, min(self.end, other.end) - max(self.start, other.start))
