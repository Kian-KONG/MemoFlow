"""知识库（Knowledge）上下文 —— 值对象。"""
from __future__ import annotations

from dataclasses import dataclass

from memoflow.domain.shared.entity import ValueObject, new_uuid


@dataclass(frozen=True)
class ChunkId(ValueObject):
    value: str

    @staticmethod
    def new() -> "ChunkId":
        return ChunkId(new_uuid())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Embedding(ValueObject):
    """文本的向量表示。使用 tuple 保证值对象不可变、可哈希。"""

    vector: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.vector) == 0:
            raise ValueError("向量不能为空")

    @property
    def dimension(self) -> int:
        return len(self.vector)

    @staticmethod
    def from_list(values: list[float]) -> "Embedding":
        return Embedding(tuple(values))
