"""会议（Meeting）上下文 —— 值对象。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from memoflow.domain.shared.entity import ValueObject, new_uuid
from memoflow.domain.shared.value_objects import TimeRange  # noqa: F401  (re-exported for convenience)


@dataclass(frozen=True)
class MeetingId(ValueObject):
    value: str

    @staticmethod
    def new() -> "MeetingId":
        return MeetingId(new_uuid())

    def __str__(self) -> str:
        return self.value


class MeetingStatus(str, Enum):
    """会议处理流水线的状态机。

    UPLOADED -> TRANSCRIBING -> DIARIZING -> SUMMARIZING -> COMPLETED
    任意阶段失败 -> FAILED
    """

    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


# 合法的状态迁移表，用于 Meeting 聚合内部的不变量校验
ALLOWED_TRANSITIONS: dict[MeetingStatus, set[MeetingStatus]] = {
    MeetingStatus.UPLOADED: {MeetingStatus.TRANSCRIBING, MeetingStatus.FAILED},
    MeetingStatus.TRANSCRIBING: {MeetingStatus.DIARIZING, MeetingStatus.FAILED},
    MeetingStatus.DIARIZING: {MeetingStatus.SUMMARIZING, MeetingStatus.FAILED},
    MeetingStatus.SUMMARIZING: {MeetingStatus.COMPLETED, MeetingStatus.FAILED},
    MeetingStatus.COMPLETED: set(),
    MeetingStatus.FAILED: {MeetingStatus.TRANSCRIBING},  # 允许失败后重试
}


@dataclass(frozen=True)
class AudioFile(ValueObject):
    """上传的原始录音文件描述。"""

    storage_path: str
    original_filename: str
    content_type: str
    size_bytes: int
    duration_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.size_bytes <= 0:
            raise ValueError("音频文件大小必须大于 0")


