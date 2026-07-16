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


_DOWNLOAD_SCRIPT = "./scripts/download_asr_model.sh"
_MOSS_HF_CONFIG = "configuration_moss_transcribe_diarize.py"

ASR_BACKENDS: tuple[AsrBackendSpec, ...] = (
    AsrBackendSpec(
        key="mlx_moss",
        label="MOSS MLX（Mac 推荐，~1.8GB）",
        model_id="vanch007/mlx-MOSS-Transcribe-Diarize",
        default_path=default_asr_model_path("mlx_moss"),
        download_script=_DOWNLOAD_SCRIPT,
        source="HuggingFace 镜像",
    ),
    AsrBackendSpec(
        key="moss_hf",
        label="MOSS HF（Transformers，~1.8GB）",
        model_id="OpenMOSS/MOSS-Transcribe-Diarize",
        default_path=default_asr_model_path("moss_hf"),
        download_script=_DOWNLOAD_SCRIPT,
        source="ModelScope",
    ),
    AsrBackendSpec(
        key="vibevoice",
        label="VibeVoice ASR（~16.7GB）",
        model_id="microsoft/VibeVoice-ASR-HF",
        default_path=default_asr_model_path("vibevoice"),
        download_script=_DOWNLOAD_SCRIPT,
        source="ModelScope",
    ),
)


def _mlx_weights_present(path: Path) -> bool:
    return (path / "config.json").is_file() and (path / "model.safetensors").is_file()


def moss_hf_config_present(path: Path) -> bool:
    return (path / _MOSS_HF_CONFIG).is_file()


def is_mlx_only_weights(path: Path) -> bool:
    return _mlx_weights_present(path) and not moss_hf_config_present(path)


def _moss_hf_weights_present(path: Path) -> bool:
    if not (path / "config.json").is_file():
        return False
    if not moss_hf_config_present(path):
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
    # MLX 权重目录在含 HF 配置时也可给 moss_hf 推理
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


def resolve_moss_hf_model_path(
    configured_path: Path | None = None,
    *,
    configured_backend: str = "moss_hf",
) -> Path:
    """解析 moss_hf 可用权重路径；MLX-only 目录时尝试 HF 默认路径。"""
    model_path = resolve_model_path("moss_hf", configured_path)
    path = model_path.expanduser()
    if weights_present("moss_hf", path):
        return path

    if is_mlx_only_weights(path):
        hf_default = Path(default_asr_model_path("moss_hf"))
        if weights_present("moss_hf", hf_default):
            return hf_default
        raise moss_hf_unavailable_error(path, configured_backend)

    if _mlx_weights_present(path) or (path / "config.json").is_file():
        raise moss_hf_unavailable_error(path, configured_backend)

    return path


def moss_hf_unavailable_error(path: Path, configured_backend: str) -> RuntimeError:
    backend_note = ""
    if configured_backend == "mlx_moss":
        backend_note = "MLX 运行时不可用且当前仅有 MLX 格式权重。"
    return RuntimeError(
        f"MOSS HF 无法加载权重目录 {path}（缺少 {_MOSS_HF_CONFIG}）。"
        f"{backend_note}"
        "请运行 ./scripts/download_asr_model.sh 下载 OpenMOSS/MOSS-Transcribe-Diarize（ModelScope），"
        "或设置 MEMOFLOW_ASR_BACKEND=vibevoice。"
    )


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
    script = spec.download_script
    lines = [f"chmod +x {script}"]
    if spec.key == "mlx_moss":
        lines.append(f"{script}  # ModelScope 无 MLX 版，经 HF 镜像下载")
    else:
        lines.append(
            f"MEMOFLOW_ASR_BACKEND={spec.key} {script}  # 默认 ModelScope，USE_MODELSCOPE=0 回退 HF"
        )
    return "\n".join(lines)
