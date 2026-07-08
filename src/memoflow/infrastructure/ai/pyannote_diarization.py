"""DiarizationPort 的 pyannote 实现（说话人分离 / 识别）。

使用 pyannote.audio 官方预训练 pipeline `speaker-diarization-3.1`。
该模型需要 HuggingFace access token 并需在 HuggingFace 上接受模型使用协议。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.diarization_port import DiarizationPort, SpeakerSegment


class PyannoteDiarization(DiarizationPort):
    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.1",
        hf_token: str = "",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._hf_token = hf_token or None
        self._device = device
        self._pipeline = None
        self._load_lock = threading.Lock()

    def _ensure_pipeline_loaded(self) -> None:
        if self._pipeline is not None:
            return
        with self._load_lock:
            if self._pipeline is not None:
                return
            logger.info(f"加载 pyannote 说话人识别模型: {self._model_name} ...")
            import torch
            from pyannote.audio import Pipeline

            self._pipeline = Pipeline.from_pretrained(self._model_name, use_auth_token=self._hf_token)
            self._pipeline.to(torch.device(self._device))
            logger.info("pyannote 模型加载完成")

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    async def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        return await asyncio.to_thread(self._diarize_sync, audio_path)

    def _diarize_sync(self, audio_path: str) -> list[SpeakerSegment]:
        self._ensure_pipeline_loaded()
        assert self._pipeline is not None

        diarization = self._pipeline(audio_path)
        segments = [
            SpeakerSegment(start=turn.start, end=turn.end, speaker_label=speaker)
            for turn, _, speaker in diarization.itertracks(yield_label=True)
        ]
        segments.sort(key=lambda s: s.start)
        return segments
