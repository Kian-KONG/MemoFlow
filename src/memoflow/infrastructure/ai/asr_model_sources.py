"""ASR 模型元数据单一数据源（下载源、路径、展示文案）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DOWNLOAD_SCRIPT = "./scripts/download_asr_model.sh"
BACKENDS: Final = frozenset({"mlx_moss", "moss_hf", "vibevoice"})


@dataclass(frozen=True)
class AsrModelSource:
    backend: str
    label: str
    short_name: str
    hf_repo_id: str
    modelscope_repo_id: str | None
    default_local_dir: str
    source: str


_SOURCES: dict[str, AsrModelSource] = {
    "mlx_moss": AsrModelSource(
        backend="mlx_moss",
        label="MOSS MLX（Mac 推荐，~1.8GB）",
        short_name="MOSS MLX",
        hf_repo_id="vanch007/mlx-MOSS-Transcribe-Diarize",
        modelscope_repo_id=None,
        default_local_dir="./models/mlx-MOSS-Transcribe-Diarize",
        source="HuggingFace 镜像",
    ),
    "moss_hf": AsrModelSource(
        backend="moss_hf",
        label="MOSS HF（Transformers，~1.8GB）",
        short_name="MOSS HF",
        hf_repo_id="OpenMOSS-Team/MOSS-Transcribe-Diarize",
        modelscope_repo_id="OpenMOSS/MOSS-Transcribe-Diarize",
        default_local_dir="./models/MOSS-Transcribe-Diarize",
        source="ModelScope",
    ),
    "vibevoice": AsrModelSource(
        backend="vibevoice",
        label="VibeVoice ASR（~16.7GB）",
        short_name="VibeVoice",
        hf_repo_id="microsoft/VibeVoice-ASR-HF",
        modelscope_repo_id="microsoft/VibeVoice-ASR-HF",
        default_local_dir="./models/VibeVoice-ASR",
        source="ModelScope",
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


def catalog_model_id(backend: str) -> str:
    """设置页展示用：优先 ModelScope ID，MLX 用 HF ID。"""
    source = get_source(backend)
    return source.modelscope_repo_id or source.hf_repo_id


def backend_short_name(backend: str) -> str:
    return get_source(backend).short_name


def backend_role_label(backend: str) -> str:
    return f"语音识别 ({get_source(backend).short_name})"
