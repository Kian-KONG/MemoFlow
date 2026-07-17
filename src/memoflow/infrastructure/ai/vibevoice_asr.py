"""ASRPort 的 VibeVoice-ASR 实现（基于 Hugging Face Transformers）。

VibeVoice-ASR 在单次推理中同时完成语音识别、说话人分离与时间戳标注，
输出 Who / When / What 结构化结果，可替代 SenseVoice + pyannote 双模型流水线。

模型需预先下载到本地目录（见 scripts/download_asr_model.sh）；推理时不触发下载。
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_SOURCE = "HuggingFace"
_DEFAULT_MODEL_PATH = "./models/VibeVoice-ASR"
_CONFIG_MARKER = "config.json"
_WEIGHT_MARKERS = (
    "model.safetensors",
    "pytorch_model.bin",
    "model.pt",
    "model.bin",
)


def model_files_present(model_path: str | Path) -> bool:
    """检查本地目录是否包含可用的 VibeVoice-ASR 权重（config + 至少一个权重文件）。"""
    path = Path(model_path).expanduser()
    if not path.is_dir():
        return False
    if not (path / _CONFIG_MARKER).is_file():
        return False
    if any((path / name).is_file() for name in _WEIGHT_MARKERS):
        return True
    # 分片 safetensors（与 moss_hf 就绪检测同思路）
    return (path / "model-00000-of-00001.safetensors").is_file() or any(
        path.glob("model-*-of-*.safetensors")
    )


def _resolve_device(device: str) -> str:
    if device != "auto":
        return device
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class VibeVoiceASR(ASRPort):
    def __init__(
        self,
        model_path: str | Path = _DEFAULT_MODEL_PATH,
        device: str = "cpu",
    ) -> None:
        self._model_path = Path(model_path).expanduser()
        self._device = _resolve_device(device)
        self._processor = None
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
        """模型文件已下载到本地（无需加载到内存）。"""
        return model_files_present(self._model_path)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _missing_model_message(self) -> str:
        return (
            f"VibeVoice-ASR 模型文件未找到（{self._model_path}）。"
            "请先运行: ./scripts/download_asr_model.sh"
        )

    def _resolve_load_path(self) -> str:
        if model_files_present(self._model_path):
            return str(self._model_path)
        raise RuntimeError(self._missing_model_message())

    def _ensure_model_loaded(self, on_progress: ProgressCallback = None) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            self._load_from_local(on_progress)

    def _load_from_local(self, on_progress: ProgressCallback) -> None:
        load_path = self._resolve_load_path()
        report_progress(on_progress, 10, f"加载 VibeVoice-ASR · {load_path}")
        logger.info(f"加载 VibeVoice-ASR 模型: {load_path} (device={self._device}) ...")

        from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration

        self._processor = AutoProcessor.from_pretrained(load_path)
        load_kwargs = self._model_load_kwargs()
        self._model = VibeVoiceAsrForConditionalGeneration.from_pretrained(load_path, **load_kwargs)
        if self._device != "cuda":
            import torch

            self._model = self._model.to(torch.device(self._device))

        report_progress(on_progress, 100, "VibeVoice-ASR 已就绪")
        logger.info("VibeVoice-ASR 模型加载完成")

    def _model_load_kwargs(self) -> dict:
        if self._device == "cuda":
            return {"device_map": "auto"}
        return {}

    async def preload(self, on_progress: ProgressCallback = None) -> None:
        await asyncio.to_thread(self._ensure_model_loaded, on_progress)

    def _require_loaded(self) -> None:
        if self._model is None or self._processor is None:
            if not self.is_ready:
                raise RuntimeError(self._missing_model_message())
            raise RuntimeError("VibeVoice-ASR 模型尚未加载到内存，请稍后重试。")

    async def transcribe(self, audio_path: str) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> ASRResult:
        self._ensure_model_loaded()
        assert self._model is not None
        assert self._processor is not None

        inputs = self._processor.apply_transcription_request(audio=audio_path).to(
            self._model.device,
            self._model.dtype,
        )
        output_ids = self._model.generate(**inputs)
        generated_ids = output_ids[:, inputs["input_ids"].shape[1] :]
        parsed = self._processor.decode(generated_ids, return_format="parsed")[0]

        segments = self._parse_segments(parsed)
        return ASRResult(language="auto", segments=segments)

    def _parse_segments(self, parsed: object) -> list[ASRSegment]:
        if not isinstance(parsed, list):
            logger.warning(f"VibeVoice-ASR 输出无法解析为分段列表: {type(parsed)!r}")
            return []

        segments: list[ASRSegment] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            text = str(item.get("Content", "")).strip()
            if not text:
                continue
            start = float(item.get("Start", 0.0))
            end = float(item.get("End", start))
            speaker = item.get("Speaker")
            speaker_label = self._format_speaker_label(speaker) if speaker is not None else None
            segments.append(
                ASRSegment(
                    start=start,
                    end=end,
                    text=text,
                    confidence=None,
                    speaker_label=speaker_label,
                )
            )
        return segments

    @staticmethod
    def _format_speaker_label(speaker: int | str) -> str:
        if isinstance(speaker, str):
            if speaker.startswith("SPEAKER_"):
                return speaker
            try:
                speaker_num = int(speaker)
            except ValueError:
                return speaker
            return f"SPEAKER_{speaker_num:02d}"
        return f"SPEAKER_{speaker:02d}"
