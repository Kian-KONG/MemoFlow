"""ASR 模型下载源映射（Hugging Face / ModelScope）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

BACKENDS: Final = frozenset({"mlx_moss", "moss_hf", "vibevoice"})


@dataclass(frozen=True)
class AsrModelSource:
    backend: str
    hf_repo_id: str
    modelscope_repo_id: str | None
    default_local_dir: str


_SOURCES: dict[str, AsrModelSource] = {
    "mlx_moss": AsrModelSource(
        backend="mlx_moss",
        hf_repo_id="vanch007/mlx-MOSS-Transcribe-Diarize",
        modelscope_repo_id=None,  # ModelScope 无此模型，仅 HF 镜像
        default_local_dir="./models/mlx-MOSS-Transcribe-Diarize",
    ),
    "moss_hf": AsrModelSource(
        backend="moss_hf",
        hf_repo_id="OpenMOSS-Team/MOSS-Transcribe-Diarize",
        modelscope_repo_id="OpenMOSS/MOSS-Transcribe-Diarize",
        default_local_dir="./models/MOSS-Transcribe-Diarize",
    ),
    "vibevoice": AsrModelSource(
        backend="vibevoice",
        hf_repo_id="microsoft/VibeVoice-ASR-HF",
        modelscope_repo_id="microsoft/VibeVoice-ASR-HF",
        default_local_dir="./models/VibeVoice-ASR",
    ),
}


def get_source(backend: str) -> AsrModelSource:
    key = backend.strip().lower()
    if key not in _SOURCES:
        raise KeyError(f"未知 ASR backend: {backend}（可选: {', '.join(sorted(BACKENDS))}）")
    return _SOURCES[key]


def modelscope_repo_for_backend(backend: str) -> str | None:
    return get_source(backend).modelscope_repo_id


def hf_repo_for_backend(backend: str) -> str:
    return get_source(backend).hf_repo_id


def default_local_dir_for_backend(backend: str) -> str:
    return get_source(backend).default_local_dir
