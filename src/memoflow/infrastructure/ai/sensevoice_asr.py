"""ASRPort 的 SenseVoice 实现（基于 FunASR）。

SenseVoice-Small 是阿里达摩院开源的多语言语音识别模型，支持中/英/粤/日/韩等语言，
自带 ITN（逆文本正则化）与情感/事件标签能力。这里通过 FunASR 的 `AutoModel` 加载，
并集成 FSMN-VAD 做语音活动检测，从而获得分句时间戳（供后续与 pyannote 说话人片段对齐）。

模型在首次调用时才会被加载（懒加载），加载与推理均为阻塞操作，
通过 `asyncio.to_thread` 包装避免阻塞事件循环。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment


class SenseVoiceASR(ASRPort):
    def __init__(self, model_name: str = "iic/SenseVoiceSmall", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._load_lock = threading.Lock()

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            logger.info(f"加载 SenseVoice 模型: {self._model_name} (device={self._device}) ...")
            from funasr import AutoModel  # 延迟导入，避免未使用该适配器时也强制安装依赖

            self._model = AutoModel(
                model=self._model_name,
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device=self._device,
                disable_update=True,
            )
            logger.info("SenseVoice 模型加载完成")

    async def transcribe(self, audio_path: str) -> ASRResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> ASRResult:
        self._ensure_model_loaded()
        assert self._model is not None

        raw_results = self._model.generate(
            input=audio_path,
            cache={},
            language="auto",
            use_itn=True,
            batch_size_s=60,
            merge_vad=False,  # 保留 VAD 分段边界，逐段生成时间戳
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
        except Exception:  # noqa: BLE001 - 后处理失败时退回原始文本，不影响主流程
            return raw_text.strip()

    @staticmethod
    def _extract_time_range(item: dict) -> tuple[float, float]:
        """从 FunASR 返回项中提取该片段的起止时间（秒）。

        当 VAD 分段信息不可用时，退化为 (0.0, 0.0)，
        上层应用会据此判断该片段无法与说话人片段对齐。
        """
        timestamp = item.get("timestamp")
        if timestamp:
            start_ms = timestamp[0][0]
            end_ms = timestamp[-1][1]
            return start_ms / 1000.0, end_ms / 1000.0
        return 0.0, 0.0
