"""ASR 后端目录、路径解析与权重就绪检测。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from memoflow.infrastructure.ai.asr_defaults import (
    default_asr_backend,
    default_asr_model_id,
    default_asr_model_path,
)


@dataclass(frozen=True)
class AsrBackendSpec:
    key: str
    label: str
    model_id: str
    default_path: str
    download_script: str
    source: str


ASR_BACKENDS: tuple[AsrBackendSpec, ...] = (
    AsrBackendSpec(
        key="mlx_moss",
        label="MOSS MLX（Mac 推荐，~1.8GB）",
        model_id="vanch007/mlx-MOSS-Transcribe-Diarize",
        default_path=default_asr_model_path("mlx_moss"),
        download_script="./scripts/download_mlx_moss.sh",
        source="OpenMOSS/MLX",
    ),
    AsrBackendSpec(
        key="moss_hf",
        label="MOSS HF（Transformers，~1.8GB）",
        model_id="OpenMOSS-Team/MOSS-Transcribe-Diarize",
        default_path=default_asr_model_path("moss_hf"),
        download_script="./scripts/download_asr_model.sh",
        source="OpenMOSS/HF",
    ),
    AsrBackendSpec(
        key="vibevoice",
        label="VibeVoice ASR（~16.7GB）",
        model_id="microsoft/VibeVoice-ASR-HF",
        default_path=default_asr_model_path("vibevoice"),
        download_script="./scripts/download_vibevoice_asr.sh",
        source="Microsoft/HF",
    ),
)


def _mlx_weights_present(path: Path) -> bool:
    return (path / "config.json").is_file() and (path / "model.safetensors").is_file()


def _moss_hf_weights_present(path: Path) -> bool:
    if not (path / "config.json").is_file():
        return False
    return (path / "model.safetensors").is_file() or (
        path / "model-00000-of-00001.safetensors"
    ).is_file()


def _vibevoice_weights_present(path: Path) -> bool:
    from memoflow.infrastructure.ai.vibevoice_asr import model_files_present

    return model_files_present(path)


_WEIGHT_CHECKERS: dict[str, Callable[[Path], bool]] = {
    "mlx_moss": _mlx_weights_present,
    "moss_hf": _moss_hf_weights_present,
    "vibevoice": _vibevoice_weights_present,
}


def weights_present(backend: str, path: str | Path) -> bool:
    checker = _WEIGHT_CHECKERS.get(backend)
    if checker is None:
        return False
    return checker(Path(path).expanduser())


def backend_spec(backend: str) -> AsrBackendSpec | None:
    for spec in ASR_BACKENDS:
        if spec.key == backend:
            return spec
    return None


def candidate_paths(backend: str, configured_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if configured_path is not None:
        paths.append(configured_path.expanduser())
    default = Path(default_asr_model_path(backend))
    if default not in paths:
        paths.append(default)
    # MLX 权重目录也可给 moss_hf 推理（同目录 config + model.safetensors）
    if backend == "moss_hf":
        mlx_path = Path(default_asr_model_path("mlx_moss"))
        if mlx_path not in paths:
            paths.append(mlx_path)
    return paths


def resolve_model_path(backend: str, configured_path: Path | None = None) -> Path:
    for path in candidate_paths(backend, configured_path):
        if weights_present(backend, path):
            return path
    if configured_path is not None and str(configured_path) not in {"", "."}:
        return configured_path.expanduser()
    return Path(default_asr_model_path(backend))


def mlx_runtime_available() -> bool:
    try:
        from moss_transcribe_diarize.mlx import load_model  # noqa: F401

        return True
    except ImportError:
        return False


def resolve_active_backend(configured_backend: str) -> str:
    backend = (configured_backend or "auto").strip().lower()
    if backend == "auto":
        backend = default_asr_backend()
    if backend == "mlx_moss" and not mlx_runtime_available():
        return "moss_hf"
    return backend


def download_command(spec: AsrBackendSpec) -> str:
    if spec.key == "mlx_moss":
        return f"chmod +x {spec.download_script}\n{spec.download_script}"
    if spec.key == "moss_hf":
        return (
            f"chmod +x {spec.download_script}\n"
            f"MEMOFLOW_ASR_BACKEND=moss_hf {spec.download_script}"
        )
    return f"chmod +x {spec.download_script}\n{spec.download_script}"
