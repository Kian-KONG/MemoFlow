"""会议（Meeting）上下文 —— 领域服务。

领域服务用于承载不天然属于某个实体/值对象、但仍是纯业务规则的逻辑
（不依赖任何基础设施，如文件系统、数据库、AI 模型）。
"""
from __future__ import annotations

from pathlib import Path

from memoflow.domain.meeting.value_objects import AudioFile
from memoflow.domain.shared.exceptions import InvariantViolationError

_EXTENSION_TO_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
}
_GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

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
    def normalize_content_type(content_type: str, filename: str) -> str:
        """浏览器 / NiceGUI 上传时经常只给 application/octet-stream，按扩展名推断真实 MIME。"""
        normalized = (content_type or "").strip().lower()
        if normalized in _ALLOWED_CONTENT_TYPES:
            return normalized
        if normalized in _GENERIC_MIME_TYPES:
            inferred = _EXTENSION_TO_MIME.get(Path(filename).suffix.lower())
            if inferred:
                return inferred
        return normalized or "application/octet-stream"

    @staticmethod
    def validate(audio: AudioFile) -> None:
        if audio.content_type not in _ALLOWED_CONTENT_TYPES:
            raise InvariantViolationError(
                f"不支持的音频格式: {audio.content_type}（支持 mp3 / wav / m4a / flac / ogg）"
            )
        if audio.size_bytes > _MAX_SIZE_BYTES:
            raise InvariantViolationError("音频文件超过 2GB 限制")
