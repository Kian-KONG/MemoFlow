"""模型与依赖就绪检查：设置页展示本地 ASR 模型与远程 API 密钥状态。"""
from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from memoflow.application.ports.asr_port import ASRPort
from memoflow.config import Settings
from memoflow.infrastructure.ai.asr_defaults import default_asr_backend, default_asr_model_path
from memoflow.infrastructure.ai.asr_status import (
    ASR_BACKENDS,
    backend_spec,
    download_command,
    mlx_runtime_available,
    resolve_active_backend,
    resolve_model_path,
    weights_present,
)

_DOWNLOAD_SCRIPT = "./scripts/download_asr_model.sh"


@dataclass(frozen=True)
class AsrOptionStatus:
    backend: str
    label: str
    model_id: str
    model_path: str
    ready: bool
    source: str
    configured: bool
    active: bool
    download_command: str
    hint: str


@dataclass(frozen=True)
class SystemStatusDTO:
    platform: str
    dependencies: list[DependencyStatus]
    models: list[ModelStatus]
    asr_options: list[AsrOptionStatus] = field(default_factory=list)
    configured_asr_backend: str = ""
    active_asr_backend: str = ""
    all_ready: bool = False


class ModelKey(str, Enum):
    ASR = "asr"


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


class ModelNotReadyError(RuntimeError):
    """处理流水线启动时发现模型或 API 尚未就绪。"""


class ModelService:
    def __init__(self, settings: Settings, asr: ASRPort) -> None:
        self._settings = settings
        self._asr = asr

    def get_status(self) -> SystemStatusDTO:
        dependencies = self._check_dependencies()
        configured = (self._settings.asr_backend or "auto").strip().lower()
        active = getattr(self._asr, "_backend_key", None) or resolve_active_backend(configured)
        asr_options = self._check_asr_options(configured, active)
        models = self._check_models(configured, active)
        all_ready = all(d.available for d in dependencies) and all(m.ready for m in models)
        return SystemStatusDTO(
            platform=f"{platform.system()} {platform.machine()}",
            dependencies=dependencies,
            models=models,
            asr_options=asr_options,
            configured_asr_backend=configured,
            active_asr_backend=active,
            all_ready=all_ready,
        )

    def get_missing_for_processing(self) -> list[str]:
        """返回尚未就绪、会导致处理失败的依赖或模型名称列表。"""
        missing: list[str] = []
        for dep in self.get_status().dependencies:
            if not dep.available:
                missing.append(dep.name)
        for model in self.get_status().models:
            if not model.ready:
                missing.append(model.role)
        return missing

    def ensure_processing_models_ready(self) -> None:
        missing = self.get_missing_for_processing()
        if missing:
            roles = "、".join(missing)
            raise ModelNotReadyError(
                f"以下依赖尚未就绪：{roles}。"
                f"请配置 API 密钥并运行 {_DOWNLOAD_SCRIPT} 下载 ASR 模型。"
            )

    async def download_model(self, key: ModelKey) -> None:
        raise RuntimeError(
            f"模型下载已改为脚本方式，请运行: {_DOWNLOAD_SCRIPT}"
        )

    async def download_all(self) -> None:
        raise RuntimeError(
            f"模型下载已改为脚本方式，请运行: {_DOWNLOAD_SCRIPT}"
        )

    def _check_dependencies(self) -> list[DependencyStatus]:
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        if self._settings.bosch_aigc_api_key.strip():
            api_keys = [
                (
                    "Bosch AIGC API",
                    self._settings.bosch_aigc_api_key,
                    "在 .env 设置 BOSCH_AIGC_API_KEY",
                ),
            ]
        else:
            api_keys = [
                ("LLM API", self._settings.resolved_llm_api_key, "设置 MEMOFLOW_DEEPSEEK_API_KEY 或 BOSCH_AIGC_API_KEY"),
                (
                    "Embedding API",
                    self._settings.resolved_embedding_api_key,
                    "设置 MEMOFLOW_OPENAI_API_KEY 或 BOSCH_AIGC_API_KEY",
                ),
                (
                    "Rerank API",
                    self._settings.resolved_rerank_api_key,
                    "设置 MEMOFLOW_RERANK_API_KEY 或 BOSCH_AIGC_API_KEY",
                ),
            ]
        return [
            DependencyStatus(
                name="ffmpeg",
                available=ffmpeg_ok,
                hint="已安装" if ffmpeg_ok else "未安装 — 请运行 brew install ffmpeg",
            ),
            *[
                DependencyStatus(
                    name=name,
                    available=bool(key.strip()),
                    hint="已配置" if key.strip() else hint,
                )
                for name, key, hint in api_keys
            ],
        ]

    def _check_models(self, configured: str, active: str) -> list[ModelStatus]:
        files_present = self._asr_files_present()
        loaded = self._asr_loaded()
        model_path = str(getattr(self._asr, "model_path", self._settings.asr_model_path))
        model_id = self._settings.asr_model_id or model_path
        role = self._asr_role_label(active)
        spec = backend_spec(active)

        if loaded:
            status, hint = "已就绪", f"{role} 已加载到内存"
        elif files_present:
            status, hint = "未加载", f"模型文件已存在（{model_path}），处理会议时将自动加载"
        else:
            script = spec.download_script if spec else _DOWNLOAD_SCRIPT
            status, hint = "未找到", f"请运行 {script} 下载权重到 {model_path}"

        if configured == "mlx_moss" and active == "moss_hf" and not mlx_runtime_available():
            hint = (
                f"{hint}；配置为 MLX，但 MLX 运行时未安装，当前以 moss_hf 检测路径 {model_path}"
            )

        return [
            ModelStatus(
                key=ModelKey.ASR,
                role=role,
                model_id=model_id,
                loaded=loaded,
                ready=files_present,
                downloading=False,
                source=getattr(self._asr, "source", spec.source if spec else "本地权重"),
                progress_percent=100.0 if loaded else 0.0,
                progress_message="",
                recent_logs=[],
                status=status,
                hint=hint,
            ),
        ]

    def _check_asr_options(self, configured: str, active: str) -> list[AsrOptionStatus]:
        configured_for = configured if configured != "auto" else default_asr_backend()
        options: list[AsrOptionStatus] = []
        for spec in ASR_BACKENDS:
            if configured_for == spec.key:
                path = resolve_model_path(spec.key, self._settings.asr_model_path)
            else:
                path = Path(default_asr_model_path(spec.key))
            ready = weights_present(spec.key, path)
            hints: list[str] = []
            if spec.key == "mlx_moss" and not mlx_runtime_available():
                hints.append("需 pip install -e \".[mlx-moss-asr]\"（上游 MLX 模块尚未发布时可改用 moss_hf）")
            if spec.key == "moss_hf":
                hints.append('需 pip install -e ".[moss-asr]"')
            if not ready:
                hints.append(f"运行: {download_command(spec).splitlines()[-1]}")
            options.append(
                AsrOptionStatus(
                    backend=spec.key,
                    label=spec.label,
                    model_id=spec.model_id,
                    model_path=str(path),
                    ready=ready,
                    source=spec.source,
                    configured=configured_for == spec.key,
                    active=active == spec.key,
                    download_command=download_command(spec),
                    hint="；".join(hints) if hints else ("当前使用" if active == spec.key else "可选"),
                )
            )
        return options

    @staticmethod
    def _asr_role_label(backend: str) -> str:
        labels = {
            "mlx_moss": "语音识别 (MOSS MLX)",
            "moss_hf": "语音识别 (MOSS HF)",
            "vibevoice": "语音识别 (VibeVoice ASR)",
        }
        return labels.get(backend, f"语音识别 ({backend})")

    def _asr_files_present(self) -> bool:
        is_ready = getattr(self._asr, "is_ready", None)
        if is_ready is not None:
            return bool(is_ready)
        from memoflow.infrastructure.ai.vibevoice_asr import model_files_present

        return model_files_present(self._settings.asr_model_path)

    def _asr_loaded(self) -> bool:
        if hasattr(self._asr, "is_loaded"):
            return bool(self._asr.is_loaded)  # type: ignore[attr-defined]
        return False


# 兼容旧名称
SystemStatusService = ModelService
