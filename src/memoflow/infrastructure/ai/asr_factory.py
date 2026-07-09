"""ASR 后端工厂：按配置装配 VibeVoice / MOSS HF / MOSS MLX。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.ports.asr_port import ASRPort
from memoflow.config import Settings
from memoflow.infrastructure.ai.asr_defaults import (
    default_asr_backend,
    default_asr_model_id,
    default_asr_model_path,
)


def _mlx_runtime_available() -> bool:
    try:
        from moss_transcribe_diarize.mlx import load_model  # noqa: F401

        return True
    except ImportError:
        return False


def build_asr(settings: Settings) -> ASRPort:
    backend = (settings.asr_backend or "auto").strip().lower()
    if backend == "auto":
        backend = default_asr_backend()

    model_path = settings.asr_model_path
    model_id = settings.asr_model_id

    if backend == "mlx_moss":
        if _mlx_runtime_available():
            from memoflow.infrastructure.ai.moss_mlx_asr import MossMLXASR

            return MossMLXASR(
                model_path=model_path,
                model_id=model_id,
                max_tokens=settings.asr_max_tokens,
            )
        logger.warning(
            "MLX MOSS 运行时未安装（moss_transcribe_diarize.mlx），回退到 moss_hf。"
            "安装: pip install -e \".[mlx-moss-asr]\""
        )
        backend = "moss_hf"
        if model_id.startswith("vanch007/"):
            model_id = default_asr_model_id("moss_hf")
            hf_path = settings.asr_model_path.parent / "MOSS-Transcribe-Diarize"
            model_path = hf_path if hf_path.is_dir() else settings.asr_model_path.parent / model_id.split("/")[-1]

    if backend == "moss_hf":
        from memoflow.infrastructure.ai.moss_hf_asr import MossHFASR

        return MossHFASR(
            model_path=model_path,
            model_id=model_id,
            device=settings.asr_device,
            max_new_tokens=settings.asr_max_tokens,
        )

    if backend == "vibevoice":
        from memoflow.infrastructure.ai.vibevoice_asr import VibeVoiceASR

        return VibeVoiceASR(model_path=model_path, device=settings.asr_device)

    raise ValueError(
        f"未知 ASR 后端: {backend!r}。"
        "可选: mlx_moss | moss_hf | vibevoice | auto"
    )
