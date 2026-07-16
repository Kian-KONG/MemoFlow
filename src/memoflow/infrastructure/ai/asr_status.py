"""ASR 后端目录、路径解析与权重就绪检测。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from memoflow.infrastructure.ai.asr_defaults import default_asr_backend, default_asr_model_path
from memoflow.infrastructure.ai.asr_model_sources import (
    DOWNLOAD_SCRIPT,
    catalog_model_id,
    get_source,
)

_MOSS_HF_CONFIG = "configuration_moss_transcribe_diarize.py"


@dataclass(frozen=True)
class AsrBackendSpec:
    key: str
    label: str
    model_id: str
    default_path: str
    download_script: str
    source: str


def _build_backend_specs() -> tuple[AsrBackendSpec, ...]:
    specs: list[AsrBackendSpec] = []
    for backend in ("mlx_moss", "moss_hf", "vibevoice"):
        src = get_source(backend)
        specs.append(
            AsrBackendSpec(
                key=backend,
                label=src.label,
                model_id=catalog_model_id(backend),
                default_path=src.default_local_dir,
                download_script=DOWNLOAD_SCRIPT,
                source=src.source,
            )
        )
    return tuple(specs)


ASR_BACKENDS: tuple[AsrBackendSpec, ...] = _build_backend_specs()


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


def backend_short_name(backend: str) -> str:
    spec = backend_spec(backend)
    if spec is None:
        return backend
    return get_source(backend).short_name


def candidate_paths(backend: str, configured_path: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if configured_path is not None:
        paths.append(configured_path.expanduser())
    default = Path(default_asr_model_path(backend))
    if default not in paths:
        paths.append(default)
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
        f"请运行 {DOWNLOAD_SCRIPT} 下载 OpenMOSS/MOSS-Transcribe-Diarize（ModelScope）。"
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
