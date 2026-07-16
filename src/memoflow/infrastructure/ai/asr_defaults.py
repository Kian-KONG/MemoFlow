"""ASR 默认后端与模型路径（避免 config ↔ factory 循环导入）。"""
from __future__ import annotations

import platform

from memoflow.infrastructure.ai.asr_model_sources import (
    default_local_dir_for_backend,
    hf_repo_for_backend,
)


def default_asr_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}:
        return "mlx_moss"
    return "vibevoice"


def default_asr_model_id(backend: str | None = None) -> str:
    return hf_repo_for_backend(backend or default_asr_backend())


def default_asr_model_path(backend: str | None = None, model_id: str | None = None) -> str:
    return default_local_dir_for_backend(backend or default_asr_backend())
