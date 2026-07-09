"""ASRPort 的 SenseVoice 实现（基于 FunASR）。

SenseVoice-Small 是阿里达摩院开源的多语言语音识别模型，支持中/英/粤/日/韩等语言，
自带 ITN（逆文本正则化）与情感/事件标签能力。这里通过 FunASR 的 `AutoModel` 加载，
并集成 FSMN-VAD 做语音活动检测，从而获得分句时间戳（供后续与 pyannote 说话人片段对齐）。

模型通过设置页从 ModelScope 预下载；推理时不再触发下载。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.infrastructure.ai.modelscope_download import sensevoice_model_ids, snapshot_download_with_progress
from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_SOURCE = "ModelScope"


class SenseVoiceASR(ASRPort):
    def __init__(self, model_name: str = "iic/SenseVoiceSmall", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._load_lock = threading.Lock()

    @property
    def source(self) -> str:
        return _SOURCE

    def _ensure_model_loaded(self, on_progress: ProgressCallback = None) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            self._download_and_load(on_progress)

    def _download_and_load(self, on_progress: ProgressCallback) -> None:
        model_ids = sensevoice_model_ids(self._model_name)
        step = 85 / len(model_ids)
        for index, model_id in enumerate(model_ids):
            start = 5 + step * index
            end = 5 + step * (index + 1)
            snapshot_download_with_progress(
                model_id,
                on_progress,
                progress_range=(start, end),
                label=model_id,
            )

        report_progress(on_progress, 92, "加载 SenseVoice 到内存...")
        logger.info(f"加载 SenseVoice 模型: {self._model_name} (device={self._device}) ...")
        from funasr import AutoModel

        self._model = AutoModel(
            model=self._model_name,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=self._device,
            disable_update=True,
        )
        report_progress(on_progress, 100, "SenseVoice 已就绪")
        logger.info("SenseVoice 模型加载完成")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def preload(self, on_progress: ProgressCallback = None) -> None:
        await asyncio.to_thread(self._ensure_model_loaded, on_progress)

    def _require_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError("SenseVoice 模型尚未下载，请前往设置页下载后再处理会议。")

    async def transcribe(self, audio_path: str) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> ASRResult:
        self._require_loaded()
        assert self._model is not None

        raw_results = self._model.generate(
            input=audio_path,
            cache={},
            language="auto",
            use_itn=True,
            batch_size_s=60,
            merge_vad=False,
        )

        segments: list[ASRSegment] = []
        detected_language = "auto"
        for item in raw_results:
            text = self._clean_text(item.get("text", ""))
            if not text:
                continue
            start, end = self._extract_time_range(item)
            segments.append(ASRSegment(start=start, end=end, text=text, confidence=None))

        return ASRResult(language=detected_language, segments=segments)

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        try:
            from funasr.utils.postprocess_utils import rich_transcription_postprocess

            return rich_transcription_postprocess(raw_text).strip()
        except Exception:  # noqa: BLE001
            return raw_text.strip()

    @staticmethod
    def _extract_time_range(item: dict) -> tuple[float, float]:
        timestamp = item.get("timestamp")
        if timestamp:
            start_ms = timestamp[0][0]
            end_ms = timestamp[-1][1]
            return start_ms / 1000.0, end_ms / 1000.0
        return 0.0, 0.0
