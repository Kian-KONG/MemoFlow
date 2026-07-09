"""MOSS-Transcribe-Diarize MLX backend (vanch007/mlx-MOSS-Transcribe-Diarize on Apple Silicon)."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.infrastructure.ai.moss_transcript import moss_speaker_label, parse_moss_transcript
from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_SOURCE = "OpenMOSS/MLX"
_MODEL_MARKERS = ("config.json", "model.safetensors", "mlx_conversion.json")


def model_files_present(model_path: str | Path) -> bool:
    path = Path(model_path).expanduser()
    if not path.is_dir():
        return False
    return all((path / name).is_file() for name in ("config.json", "model.safetensors"))


class MossMLXASR(ASRPort):
    def __init__(
        self,
        model_path: str | Path,
        *,
        model_id: str | None = None,
        max_tokens: int = 4096,
        strict: bool = True,
    ) -> None:
        self._model_path = Path(model_path).expanduser()
        self._model_id = model_id or str(model_path)
        self._max_tokens = max_tokens
        self._strict = strict
        self._model = None
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
        return self._model is not None

    def _missing_model_message(self) -> str:
        return (
            f"MLX MOSS 模型未找到（{self._model_path}）。"
            "请先运行: ./scripts/download_asr_model.sh"
        )

    def _resolve_model_ref(self) -> str:
        if model_files_present(self._model_path):
            return str(self._model_path)
        if "/" in self._model_id:
            return self._model_id
        raise RuntimeError(self._missing_model_message())

    def _ensure_model_loaded(self, on_progress: ProgressCallback = None) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            self._load_from_local(on_progress)

    def _load_from_local(self, on_progress: ProgressCallback) -> None:
        model_ref = self._resolve_model_ref()
        report_progress(on_progress, 10, f"加载 MLX MOSS · {model_ref}")
        logger.info(f"加载 MLX MOSS 模型: {model_ref} ...")

        try:
            from moss_transcribe_diarize.mlx import load_model
        except ImportError as exc:
            raise RuntimeError(
                "未安装 MLX 运行时。请运行: pip install -e \".[mlx-moss-asr]\" "
                "或将 MEMOFLOW_ASR_BACKEND 设为 moss_hf。"
            ) from exc

        self._model = load_model(model_ref, strict=self._strict)
        report_progress(on_progress, 100, "MLX MOSS 已就绪")
        logger.info("MLX MOSS 模型加载完成")

    async def preload(self, on_progress: ProgressCallback = None) -> None:
        await asyncio.to_thread(self._ensure_model_loaded, on_progress)

    async def transcribe(self, audio_path: str) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> ASRResult:
        self._ensure_model_loaded()
        assert self._model is not None

        result = self._model.generate(
            audio_path,
            max_tokens=self._max_tokens,
            temperature=0.0,
        )
        text = getattr(result, "text", str(result))
        segments = self._parse_segments(text)
        return ASRResult(language="auto", segments=segments)

    def _parse_segments(self, text: str) -> list[ASRSegment]:
        parsed = parse_moss_transcript(text)
        if not parsed:
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
