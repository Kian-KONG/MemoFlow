from pathlib import Path

import pytest

from memoflow.infrastructure.ai.asr_status import (
    ASR_BACKENDS,
    candidate_paths,
    download_command,
    is_mlx_only_weights,
    moss_hf_config_present,
    resolve_active_backend,
    resolve_model_path,
    resolve_moss_hf_model_path,
    weights_present,
)

_MOSS_HF_CONFIG = "configuration_moss_transcribe_diarize.py"


def _patch_default_paths(monkeypatch, tmp_path: Path):
    def fake_default(backend: str | None = None, model_id: str | None = None) -> str:
        key = backend or "moss_hf"
        folder = {
            "mlx_moss": "mlx-MOSS-Transcribe-Diarize",
            "moss_hf": "MOSS-Transcribe-Diarize",
            "vibevoice": "VibeVoice-ASR",
        }[key]
        return str(tmp_path / folder)

    monkeypatch.setattr(
        "memoflow.infrastructure.ai.asr_status.default_asr_model_path",
        fake_default,
    )
    return fake_default


def _write_mlx_weights(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "model.safetensors").write_bytes(b"x" * 128)


def _write_moss_hf_weights(path: Path, *, sharded: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / _MOSS_HF_CONFIG).write_text("# moss config", encoding="utf-8")
    if sharded:
        (path / "model-00000-of-00001.safetensors").write_bytes(b"x" * 64)
    else:
        (path / "model.safetensors").write_bytes(b"x" * 128)


def test_resolve_model_path_does_not_treat_mlx_only_as_moss_hf(tmp_path: Path, monkeypatch):
    mlx_dir = tmp_path / "mlx-MOSS-Transcribe-Diarize"
    vibevoice = tmp_path / "VibeVoice-ASR"
    _write_mlx_weights(mlx_dir)
    _patch_default_paths(monkeypatch, tmp_path)

    resolved = resolve_model_path("moss_hf", vibevoice)
    assert resolved == vibevoice
    assert is_mlx_only_weights(mlx_dir)
    assert not weights_present("moss_hf", mlx_dir)


def test_resolve_model_path_prefers_configured_dir_when_weights_present(tmp_path: Path, monkeypatch):
    configured = tmp_path / "custom-moss"
    default = tmp_path / "MOSS-Transcribe-Diarize"
    _write_moss_hf_weights(configured)
    _patch_default_paths(monkeypatch, tmp_path)

    resolved = resolve_model_path("moss_hf", configured)
    assert resolved == configured
    assert not weights_present("moss_hf", default)


def test_resolve_model_path_returns_configured_when_no_weights(tmp_path: Path, monkeypatch):
    configured = tmp_path / "empty-custom"
    configured.mkdir()
    _patch_default_paths(monkeypatch, tmp_path)

    resolved = resolve_model_path("moss_hf", configured)
    assert resolved == configured


def test_resolve_model_path_returns_default_when_no_configured_path(tmp_path: Path, monkeypatch):
    fake_default = _patch_default_paths(monkeypatch, tmp_path)

    resolved = resolve_model_path("moss_hf", None)
    assert resolved == Path(fake_default("moss_hf"))


def test_resolve_model_path_ignores_empty_configured_path(tmp_path: Path, monkeypatch):
    fake_default = _patch_default_paths(monkeypatch, tmp_path)

    resolved = resolve_model_path("moss_hf", Path("."))
    assert resolved == Path(fake_default("moss_hf"))


def test_resolve_moss_hf_model_path_uses_hf_default_when_only_mlx_present(tmp_path: Path, monkeypatch):
    fake_default = _patch_default_paths(monkeypatch, tmp_path)
    mlx_dir = Path(fake_default("mlx_moss"))
    hf_dir = Path(fake_default("moss_hf"))
    _write_mlx_weights(mlx_dir)
    _write_moss_hf_weights(hf_dir)

    resolved = resolve_moss_hf_model_path(mlx_dir)
    assert resolved == hf_dir


def test_resolve_moss_hf_model_path_raises_for_mlx_only_without_hf_default(tmp_path: Path, monkeypatch):
    fake_default = _patch_default_paths(monkeypatch, tmp_path)
    mlx_dir = Path(fake_default("mlx_moss"))
    _write_mlx_weights(mlx_dir)

    with pytest.raises(RuntimeError, match=_MOSS_HF_CONFIG):
        resolve_moss_hf_model_path(mlx_dir, configured_backend="mlx_moss")


def test_candidate_paths_includes_mlx_fallback_for_moss_hf(tmp_path: Path, monkeypatch):
    fake_default = _patch_default_paths(monkeypatch, tmp_path)
    configured = tmp_path / "cfg"

    paths = candidate_paths("moss_hf", configured)
    assert paths == [
        configured,
        Path(fake_default("moss_hf")),
        Path(fake_default("mlx_moss")),
    ]


@pytest.mark.parametrize(
    ("backend", "writer", "expected"),
    [
        ("mlx_moss", _write_mlx_weights, True),
        ("moss_hf", lambda p: _write_moss_hf_weights(p, sharded=False), True),
        ("moss_hf", lambda p: _write_moss_hf_weights(p, sharded=True), True),
    ],
)
def test_weights_present_detects_valid_layout(tmp_path: Path, backend, writer, expected):
    model_dir = tmp_path / backend
    writer(model_dir)
    assert weights_present(backend, model_dir) is expected


def test_weights_present_moss_hf_requires_config_and_moss_configuration(tmp_path: Path):
    model_dir = tmp_path / "partial"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"x")

    assert moss_hf_config_present(model_dir) is False
    assert weights_present("moss_hf", model_dir) is False

    (model_dir / _MOSS_HF_CONFIG).write_text("# cfg", encoding="utf-8")
    assert moss_hf_config_present(model_dir) is True
    assert weights_present("moss_hf", model_dir) is True


def test_weights_present_moss_hf_rejects_configuration_json_only(tmp_path: Path):
    model_dir = tmp_path / "wrong-config"
    model_dir.mkdir()
    (model_dir / "configuration.json").write_text("{}", encoding="utf-8")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"x")

    assert weights_present("moss_hf", model_dir) is False


def test_weights_present_unknown_backend(tmp_path: Path):
    assert weights_present("unknown", tmp_path) is False


def _write_vibevoice_partial(path: Path, *names: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for name in names:
        (path / name).write_text("{}", encoding="utf-8")


def test_weights_present_vibevoice_rejects_config_only(tmp_path: Path):
    model_dir = tmp_path / "vibevoice-partial"
    _write_vibevoice_partial(model_dir, "config.json")
    assert weights_present("vibevoice", model_dir) is False


def test_weights_present_vibevoice_rejects_tokenizer_without_weights(tmp_path: Path):
    model_dir = tmp_path / "vibevoice-tokenizer-only"
    _write_vibevoice_partial(
        model_dir,
        "config.json",
        "preprocessor_config.json",
        "tokenizer_config.json",
    )
    assert weights_present("vibevoice", model_dir) is False


def test_weights_present_vibevoice_requires_config_and_weight(tmp_path: Path):
    model_dir = tmp_path / "vibevoice-complete"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"x" * 64)
    assert weights_present("vibevoice", model_dir) is True


def test_weights_present_vibevoice_accepts_sharded_safetensors(tmp_path: Path):
    model_dir = tmp_path / "vibevoice-sharded"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model-00001-of-00002.safetensors").write_bytes(b"x" * 32)
    assert weights_present("vibevoice", model_dir) is True


def test_resolve_active_backend_falls_back_when_mlx_runtime_missing(monkeypatch):
    monkeypatch.setattr(
        "memoflow.infrastructure.ai.asr_status.mlx_runtime_available",
        lambda: False,
    )
    assert resolve_active_backend("mlx_moss") == "moss_hf"
    assert resolve_active_backend("moss_hf") == "moss_hf"


def test_download_command_mentions_modelscope_or_hf_mirror():
    by_key = {spec.key: spec for spec in ASR_BACKENDS}
    mlx_cmd = download_command(by_key["mlx_moss"])
    moss_cmd = download_command(by_key["moss_hf"])

    assert "HF" in mlx_cmd or "hf" in mlx_cmd.lower() or "镜像" in mlx_cmd
    assert "ModelScope" in moss_cmd
    assert "USE_MODELSCOPE=0" in moss_cmd
