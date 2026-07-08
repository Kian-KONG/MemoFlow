"""转写（Transcript）上下文 —— 值对象。"""
from __future__ import annotations

from dataclasses import dataclass

from memoflow.domain.shared.entity import ValueObject, new_uuid


@dataclass(frozen=True)
class TranscriptId(ValueObject):
    value: str

    @staticmethod
    def new() -> "TranscriptId":
        return TranscriptId(new_uuid())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SpeakerId(ValueObject):
    value: str

    @staticmethod
    def new() -> "SpeakerId":
        return SpeakerId(new_uuid())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class UtteranceId(ValueObject):
    value: str

    @staticmethod
    def new() -> "UtteranceId":
        return UtteranceId(new_uuid())

    def __str__(self) -> str:
        return self.value
