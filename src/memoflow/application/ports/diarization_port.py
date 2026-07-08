"""说话人识别（Speaker Diarization）端口。

生产实现：`memoflow.infrastructure.ai.pyannote_diarization.PyannoteDiarization`
（基于 pyannote.audio 的 speaker-diarization-3.1 pipeline）。
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
