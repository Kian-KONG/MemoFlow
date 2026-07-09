"""ASR（自动语音识别）端口。

生产实现：`memoflow.infrastructure.ai.vibevoice_asr.VibeVoiceASR`（基于 Microsoft VibeVoice-ASR，
单次推理同时输出转写文本、说话人标签与时间戳）。
可替换为 Whisper / Paraformer 等任意实现，只需实现本接口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ASRSegment:
    start: float
    end: float
    text: str
    confidence: float | None = None
    speaker_label: str | None = None


@dataclass(frozen=True)
class ASRResult:
    language: str
    segments: list[ASRSegment]


class ASRPort(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> ASRResult:
        """对给定路径的音频文件进行语音识别，返回带时间戳的分段文本。"""
