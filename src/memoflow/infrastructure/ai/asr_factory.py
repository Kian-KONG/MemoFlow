"""ASR 后端工厂：按配置装配 VibeVoice / MOSS HF / MOSS MLX。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort
from memoflow.config import Settings
from memoflow.infrastructure.ai.asr_defaults import default_asr_backend, default_asr_model_id
from memoflow.infrastructure.ai.asr_status import (
    mlx_runtime_available,
    resolve_active_backend,
    resolve_model_path,
)


def build_asr(settings: Settings) -> ASRPort:
    configured = (settings.asr_backend or "auto").strip().lower()
    if configured == "auto":
        configured = default_asr_backend()

    active = resolve_active_backend(configured)
    model_path = resolve_model_path(active, settings.asr_model_path)
    model_id = settings.asr_model_id

    if active == "mlx_moss":
        from memoflow.infrastructure.ai.moss_mlx_asr import MossMLXASR

        asr = MossMLXASR(
            model_path=model_path,
            model_id=model_id or default_asr_model_id("mlx_moss"),
            max_tokens=settings.asr_max_tokens,
        )
        asr._backend_key = "mlx_moss"  # type: ignore[attr-defined]
        asr._configured_backend = configured  # type: ignore[attr-defined]
        return asr

    if active == "moss_hf":
        if configured == "mlx_moss" and not mlx_runtime_available():
            logger.warning(
                "MLX 运行时不可用（moss_transcribe_diarize.mlx），已用 moss_hf 加载本地权重。"
                "安装: pip install -e \".[mlx-moss-asr]\" 可启用 MLX。"
            )
        from memoflow.infrastructure.ai.moss_hf_asr import MossHFASR

        hf_model_id = model_id
        if hf_model_id.startswith("vanch007/"):
            hf_model_id = default_asr_model_id("moss_hf")
        asr = MossHFASR(
            model_path=model_path,
            model_id=hf_model_id,
            device=settings.asr_device,
            max_new_tokens=settings.asr_max_tokens,
        )
        asr._backend_key = "moss_hf"  # type: ignore[attr-defined]
        asr._configured_backend = configured  # type: ignore[attr-defined]
        return asr

    if active == "vibevoice":
        from memoflow.infrastructure.ai.vibevoice_asr import VibeVoiceASR

        asr = VibeVoiceASR(model_path=model_path, device=settings.asr_device)
        asr._backend_key = "vibevoice"  # type: ignore[attr-defined]
        asr._configured_backend = configured  # type: ignore[attr-defined]
        return asr

    raise ValueError(
        f"未知 ASR 后端: {active!r}。"
        "可选: mlx_moss | moss_hf | vibevoice | auto"
    )
