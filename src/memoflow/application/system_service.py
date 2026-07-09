"""模型管理服务：查看状态、在设置页预下载模型（与会议处理流水线解耦）。"""
from __future__ import annotations

import asyncio
import platform
import shutil
from dataclasses import dataclass, field
from enum import Enum

from memoflow.application.ports.asr_port import ASRPort
from memoflow.application.ports.diarization_port import DiarizationPort
from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.application.ports.llm_port import LLMPort
from memoflow.config import Settings
from memoflow.infrastructure.ai.embedding_model import SentenceTransformerEmbedding
from memoflow.infrastructure.ai.pyannote_diarization import PyannoteDiarization
from memoflow.infrastructure.ai.qwen_mlx_llm import QwenMLXLLM
from memoflow.infrastructure.ai.sensevoice_asr import SenseVoiceASR


class ModelKey(str, Enum):
    ASR = "asr"
    DIARIZATION = "diarization"
    LLM = "llm"
    EMBEDDING = "embedding"


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    available: bool
    hint: str


@dataclass(frozen=True)
class ModelStatus:
    key: ModelKey
    role: str
    model_id: str
    loaded: bool
    ready: bool
    downloading: bool
    source: str
    progress_percent: float
    progress_message: str
    status: str
    hint: str
    recent_logs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SystemStatusDTO:
    platform: str
    dependencies: list[DependencyStatus]
    models: list[ModelStatus]
    all_ready: bool


class ModelNotReadyError(RuntimeError):
    """处理流水线启动时发现模型尚未在设置页下载。"""


class ModelService:
    def __init__(
        self,
        settings: Settings,
        asr: ASRPort,
        diarization: DiarizationPort,
        llm: LLMPort,
        embedding: EmbeddingPort,
    ) -> None:
        self._settings = settings
        self._asr = asr
        self._diarization = diarization
        self._llm = llm
        self._embedding = embedding
        self._downloading: set[ModelKey] = set()
        self._download_lock = asyncio.Lock()
        self._progress: dict[ModelKey, tuple[float, str, list[str]]] = {}

    def get_status(self) -> SystemStatusDTO:
        dependencies = self._check_dependencies()
        models = self._check_models()
        all_ready = all(d.available for d in dependencies) and all(
            m.loaded for m in models if m.ready
        )
        return SystemStatusDTO(
            platform=f"{platform.system()} {platform.machine()}",
            dependencies=dependencies,
            models=models,
            all_ready=all_ready,
        )

    def get_missing_for_processing(self) -> list[str]:
        """返回尚未加载、会导致处理失败的模型名称列表。"""
        missing: list[str] = []
        for model in self.get_status().models:
            if not model.ready:
                continue
            adapter = self._adapter_for(model.key)
            if hasattr(adapter, "is_loaded") and not adapter.is_loaded:
                missing.append(model.role)
        return missing

    def ensure_processing_models_ready(self) -> None:
        missing = self.get_missing_for_processing()
        if missing:
            roles = "、".join(missing)
            raise ModelNotReadyError(f"以下模型尚未下载：{roles}。请前往「设置」页面下载后再处理会议。")

    async def download_model(self, key: ModelKey) -> None:
        if key in self._downloading:
            return
        model = self._find_model(key)
        if not model.ready:
            raise RuntimeError(model.hint)
        if model.loaded:
            return

        async with self._download_lock:
            if key in self._downloading:
                return
            self._downloading.add(key)
            self._set_progress(key, 0.0, "准备开始下载...")
        try:
            await self._preload(key)
            self._set_progress(key, 100.0, "模型已就绪")
        except Exception as exc:
            message = str(exc)
            self._append_log(key, f"失败: {message}")
            if "connection" in message.lower() or "timeout" in message.lower():
                raise RuntimeError(
                    f"网络连接中断或超时，请检查网络后重试。详情: {message}"
                ) from exc
            raise
        finally:
            self._downloading.discard(key)

    async def download_all(self) -> None:
        for key in ModelKey:
            model = self._find_model(key)
            if model.ready and not model.loaded:
                await self.download_model(key)

    def _find_model(self, key: ModelKey) -> ModelStatus:
        for model in self.get_status().models:
            if model.key == key:
                return model
        raise KeyError(key)

    async def _preload(self, key: ModelKey) -> None:
        adapter = self._adapter_for(key)
        if not hasattr(adapter, "preload"):
            raise RuntimeError(f"模型 {key.value} 不支持预下载")
        await adapter.preload(lambda percent, message: self._set_progress(key, percent, message))  # type: ignore[attr-defined]

    def _adapter_for(self, key: ModelKey):  # noqa: ANN202
        return {
            ModelKey.ASR: self._asr,
            ModelKey.DIARIZATION: self._diarization,
            ModelKey.LLM: self._llm,
            ModelKey.EMBEDDING: self._embedding,
        }[key]

    def _check_dependencies(self) -> list[DependencyStatus]:
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        return [
            DependencyStatus(
                name="ffmpeg",
                available=ffmpeg_ok,
                hint="已安装" if ffmpeg_ok else "未安装 — 请运行 brew install ffmpeg",
            ),
        ]

    def _check_models(self) -> list[ModelStatus]:
        hf_configured = bool(self._settings.hf_token.strip())
        mlx_available = platform.machine() == "arm64" and platform.system() == "Darwin"

        specs = [
            (
                ModelKey.ASR,
                "语音识别 (ASR)",
                self._settings.asr_model,
                isinstance(self._asr, SenseVoiceASR) and self._asr.is_loaded,
                True,
                getattr(self._asr, "source", "ModelScope"),
                "已就绪" if isinstance(self._asr, SenseVoiceASR) and self._asr.is_loaded else "未下载",
                "在设置页点击下载，从 ModelScope 拉取 SenseVoice 模型",
            ),
            (
                ModelKey.DIARIZATION,
                "说话人识别",
                self._settings.diarization_model,
                isinstance(self._diarization, PyannoteDiarization) and self._diarization.is_loaded,
                hf_configured,
                getattr(self._diarization, "source", "HuggingFace"),
                (
                    "已就绪"
                    if isinstance(self._diarization, PyannoteDiarization) and self._diarization.is_loaded
                    else ("待配置 Token" if not hf_configured else "未下载")
                ),
                (
                    "请在 .env 设置 MEMOFLOW_HF_TOKEN 并接受 HuggingFace 模型协议"
                    if not hf_configured
                    else "在设置页点击下载 pyannote 模型"
                ),
            ),
            (
                ModelKey.LLM,
                "摘要生成 (LLM)",
                self._settings.llm_model_path,
                isinstance(self._llm, QwenMLXLLM) and self._llm.is_loaded,
                mlx_available,
                getattr(self._llm, "source", "ModelScope"),
                (
                    "已就绪"
                    if isinstance(self._llm, QwenMLXLLM) and self._llm.is_loaded
                    else ("不可用" if not mlx_available else "未下载")
                ),
                (
                    "Qwen3 MLX 仅支持 Apple Silicon Mac"
                    if not mlx_available
                    else "在设置页点击下载（约数 GB）"
                ),
            ),
            (
                ModelKey.EMBEDDING,
                "知识库 Embedding",
                self._settings.embedding_model,
                isinstance(self._embedding, SentenceTransformerEmbedding) and self._embedding.is_loaded,
                True,
                getattr(self._embedding, "source", "ModelScope"),
                (
                    "已就绪"
                    if isinstance(self._embedding, SentenceTransformerEmbedding) and self._embedding.is_loaded
                    else "未下载"
                ),
                "在设置页点击下载 Embedding 模型",
            ),
        ]
        return [
            ModelStatus(
                key=key,
                role=role,
                model_id=model_id,
                loaded=loaded,
                ready=ready,
                downloading=key in self._downloading,
                source=source,
                progress_percent=self._progress.get(key, (100.0 if loaded else 0.0, "", []))[0],
                progress_message=self._progress.get(key, (100.0 if loaded else 0.0, "", []))[1],
                recent_logs=list(self._progress.get(key, (0.0, "", []))[2]),
                status=status,
                hint=hint,
            )
            for key, role, model_id, loaded, ready, source, status, hint in specs
        ]

    def _set_progress(self, key: ModelKey, percent: float, message: str) -> None:
        _, _, logs = self._progress.get(key, (0.0, "", []))
        next_logs = [*logs]
        if not next_logs or next_logs[-1] != message:
            next_logs.append(message)
        self._progress[key] = (percent, message, next_logs[-8:])

    def _append_log(self, key: ModelKey, message: str) -> None:
        percent, current, logs = self._progress.get(key, (0.0, "", []))
        next_logs = [*logs, message]
        self._progress[key] = (percent, current, next_logs[-8:])


# 兼容旧名称
SystemStatusService = ModelService
