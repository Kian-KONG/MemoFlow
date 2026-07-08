"""会议（Meeting）上下文 —— 领域服务。

领域服务用于承载不天然属于某个实体/值对象、但仍是纯业务规则的逻辑
（不依赖任何基础设施，如文件系统、数据库、AI 模型）。
"""
from __future__ import annotations

from memoflow.domain.meeting.value_objects import AudioFile
from memoflow.domain.shared.exceptions import InvariantViolationError

_ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/flac",
    "audio/ogg",
}
_MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2GB


class AudioValidationPolicy:
    """校验上传的音频文件是否满足录入条件。"""

    @staticmethod
    def validate(audio: AudioFile) -> None:
        if audio.content_type not in _ALLOWED_CONTENT_TYPES:
            raise InvariantViolationError(f"不支持的音频格式: {audio.content_type}")
        if audio.size_bytes > _MAX_SIZE_BYTES:
            raise InvariantViolationError("音频文件超过 2GB 限制")
