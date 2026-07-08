"""系统状态服务：检查运行时依赖与本地 AI 模型就绪情况。"""
from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass

from memoflow.application.ports.asr_port import ASRPort
from memoflow.application.ports.diarization_port import DiarizationPort
from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.application.ports.llm_port import LLMPort
from memoflow.config import Settings
from memoflow.infrastructure.ai.embedding_model import SentenceTransformerEmbedding
from memoflow.infrastructure.ai.pyannote_diarization import PyannoteDiarization
from memoflow.infrastructure.ai.qwen_mlx_llm import QwenMLXLLM
from memoflow.infrastructure.ai.sensevoice_asr import SenseVoiceASR


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    available: bool
    hint: str


@dataclass(frozen=True)
class ModelStatus:
    role: str
    model_id: str
    loaded: bool
    ready: bool
    status: str
    hint: str


@dataclass(frozen=True)
class SystemStatusDTO:
    platform: str
    dependencies: list[DependencyStatus]
    models: list[ModelStatus]
    all_ready: bool


class SystemStatusService:
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

    def get_status(self) -> SystemStatusDTO:
        dependencies = self._check_dependencies()
        models = self._check_models()
        all_ready = all(d.available for d in dependencies) and all(m.ready for m in models)
        return SystemStatusDTO(
            platform=f"{platform.system()} {platform.machine()}",
            dependencies=dependencies,
            models=models,
            all_ready=all_ready,
        )

    def _check_dependencies(self) -> list[DependencyStatus]:
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        return [
            DependencyStatus(
                name="ffmpeg",
                available=ffmpeg_ok,
                hint="已安装" if ffmpeg_ok else "未安装 — m4a/mp3 等格式转写需要 ffmpeg，请运行 brew install ffmpeg",
            ),
        ]

    def _check_models(self) -> list[ModelStatus]:
        hf_configured = bool(self._settings.hf_token.strip())
        mlx_available = platform.machine() == "arm64" and platform.system() == "Darwin"

        asr_loaded = isinstance(self._asr, SenseVoiceASR) and self._asr.is_loaded
        diar_loaded = isinstance(self._diarization, PyannoteDiarization) and self._diarization.is_loaded
        llm_loaded = isinstance(self._llm, QwenMLXLLM) and self._llm.is_loaded
        emb_loaded = isinstance(self._embedding, SentenceTransformerEmbedding) and self._embedding.is_loaded

        return [
            ModelStatus(
                role="语音识别 (ASR)",
                model_id=self._settings.asr_model,
                loaded=asr_loaded,
                ready=True,
                status="已加载到内存" if asr_loaded else "待首次使用时下载/加载",
                hint="首次转写时会自动从 ModelScope 下载模型，可能需要数分钟",
            ),
            ModelStatus(
                role="说话人识别",
                model_id=self._settings.diarization_model,
                loaded=diar_loaded,
                ready=hf_configured,
                status=(
                    "已加载到内存"
                    if diar_loaded
                    else ("待配置 HuggingFace Token" if not hf_configured else "待首次使用时下载/加载")
                ),
                hint=(
                    "请在 .env 中设置 MEMOFLOW_HF_TOKEN，并在 HuggingFace 接受 pyannote 模型协议"
                    if not hf_configured
                    else "首次说话人识别时会自动下载模型"
                ),
            ),
            ModelStatus(
                role="摘要生成 (LLM)",
                model_id=self._settings.llm_model_path,
                loaded=llm_loaded,
                ready=mlx_available,
                status=(
                    "已加载到内存"
                    if llm_loaded
                    else ("需要 Apple Silicon (MLX)" if not mlx_available else "待首次使用时下载/加载")
                ),
                hint=(
                    "Qwen3 MLX 模型仅支持 Apple Silicon Mac"
                    if not mlx_available
                    else "首次生成摘要时会自动下载模型（约数 GB）"
                ),
            ),
            ModelStatus(
                role="知识库 Embedding",
                model_id=self._settings.embedding_model,
                loaded=emb_loaded,
                ready=True,
                status="已加载到内存" if emb_loaded else "待首次使用时下载/加载",
                hint="首次知识库索引时会自动下载模型",
            ),
        ]
