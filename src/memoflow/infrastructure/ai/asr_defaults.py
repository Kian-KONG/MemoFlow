"""ASR 默认后端与模型路径（避免 config ↔ factory 循环导入）。"""
from __future__ import annotations

import platform


def default_asr_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}:
        return "mlx_moss"
    return "vibevoice"


def default_asr_model_id(backend: str | None = None) -> str:
    backend = backend or default_asr_backend()
    if backend == "mlx_moss":
        return "vanch007/mlx-MOSS-Transcribe-Diarize"
    if backend == "moss_hf":
        return "OpenMOSS-Team/MOSS-Transcribe-Diarize"
    return "microsoft/VibeVoice-ASR-HF"


def default_asr_model_path(backend: str | None = None, model_id: str | None = None) -> str:
    backend = backend or default_asr_backend()
    model_id = model_id or default_asr_model_id(backend)
    folder = model_id.split("/")[-1]
    if backend == "vibevoice" and folder == "VibeVoice-ASR-HF":
        return "./models/VibeVoice-ASR"
    return f"./models/{folder}"
