"""MOSS-Transcribe-Diarize via Hugging Face transformers (OpenMOSS-Team weights)."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.infrastructure.ai.moss_transcript import moss_speaker_label, parse_moss_transcript
from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_SOURCE = "OpenMOSS/HF"
_MODEL_MARKERS = (
    "config.json",
    "model.safetensors",
    "model-00000-of-00001.safetensors",
)


def model_files_present(model_path: str | Path) -> bool:
    path = Path(model_path).expanduser()
    if not path.is_dir():
        return False
    if not (path / "config.json").is_file():
        return False
    return any((path / name).is_file() for name in _MODEL_MARKERS[1:])


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class MossHFASR(ASRPort):
    def __init__(
        self,
        model_path: str | Path,
        *,
        model_id: str | None = None,
        device: str = "auto",
        max_new_tokens: int = 4096,
    ) -> None:
        self._model_path = Path(model_path).expanduser()
        self._model_id = model_id or str(model_path)
        self._device = _resolve_device(device)
        self._max_new_tokens = max_new_tokens
        self._runner = None
        self._load_lock = threading.Lock()

    @property
    def source(self) -> str:
        return _SOURCE

    @property
    def model_path(self) -> Path:
        return self._model_path

    @property
    def is_ready(self) -> bool:
        return model_files_present(self._model_path)

    @property
    def is_loaded(self) -> bool:
        return self._runner is not None and self._runner.is_loaded

    def _missing_model_message(self) -> str:
        return (
            f"MOSS-Transcribe-Diarize 模型未找到（{self._model_path}）。"
            "请先运行: ./scripts/download_asr_model.sh"
        )

    def _resolve_load_path(self) -> str:
        if model_files_present(self._model_path):
            return str(self._model_path)
        raise RuntimeError(self._missing_model_message())

    def _ensure_model_loaded(self, on_progress: ProgressCallback = None) -> None:
        if self._runner is not None and self._runner.is_loaded:
            return
        with self._load_lock:
            if self._runner is not None and self._runner.is_loaded:
                return
            self._load_from_local(on_progress)

    def _load_from_local(self, on_progress: ProgressCallback) -> None:
        load_path = self._resolve_load_path()
        report_progress(on_progress, 10, f"加载 MOSS-Transcribe-Diarize · {load_path}")
        logger.info(f"加载 MOSS HF 模型: {load_path} (device={self._device}) ...")

        try:
            from moss_transcribe_diarize.app.model_runner import ModelRunner
        except ImportError as exc:
            raise RuntimeError(
                "未安装 moss-transcribe-diarize。请运行: pip install -e \".[moss-asr]\""
            ) from exc

        dtype = "bf16" if self._device in {"cuda", "mps"} else "fp32"
        self._runner = ModelRunner(load_path, device=self._device, dtype=dtype)
        self._runner._ensure_loaded()

        report_progress(on_progress, 100, "MOSS-Transcribe-Diarize 已就绪")
        logger.info("MOSS HF 模型加载完成")

    async def preload(self, on_progress: ProgressCallback = None) -> None:
        await asyncio.to_thread(self._ensure_model_loaded, on_progress)

    async def transcribe(self, audio_path: str) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> ASRResult:
        self._ensure_model_loaded()
        assert self._runner is not None

        result = self._runner.transcribe(
            audio_path,
            max_new_tokens=self._max_new_tokens,
            decoding="greedy",
            temperature=0.0,
        )
        segments = self._parse_segments(result.text)
        return ASRResult(language="auto", segments=segments)

    def _parse_segments(self, text: str) -> list[ASRSegment]:
        parsed = parse_moss_transcript(text)
        if not parsed:
            logger.warning("MOSS 输出未解析出分段，返回整段文本")
            stripped = text.strip()
            if not stripped:
                return []
            return [ASRSegment(start=0.0, end=0.0, text=stripped, speaker_label=None)]

        return [
            ASRSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                confidence=None,
                speaker_label=moss_speaker_label(segment.speaker),
            )
            for segment in parsed
        ]
