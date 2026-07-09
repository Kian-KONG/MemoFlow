"""说话人识别（Speaker Diarization）端口。

使用 VibeVoice ASR 时，说话人标签由 ASR 内置 diarization 提供，本端口可选。
亦可替换为 pyannote.audio 等独立说话人分离实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeakerSegment:
    start: float
    end: float
    speaker_label: str


class DiarizationPort(ABC):
    @abstractmethod
    async def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        """对给定路径的音频文件进行说话人分离，返回按时间排序的说话人片段列表。"""
