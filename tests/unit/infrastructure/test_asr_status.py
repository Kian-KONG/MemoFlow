from pathlib import Path

from memoflow.infrastructure.ai.asr_status import resolve_model_path, weights_present


def test_resolve_model_path_finds_mlx_weights_when_env_points_vibevoice(tmp_path: Path, monkeypatch):
    mlx_dir = tmp_path / "mlx-MOSS-Transcribe-Diarize"
    vibevoice = tmp_path / "VibeVoice-ASR"
    mlx_dir.mkdir(parents=True)
    (mlx_dir / "config.json").write_text("{}", encoding="utf-8")
    (mlx_dir / "model.safetensors").write_bytes(b"x" * 128)

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

    resolved = resolve_model_path("moss_hf", vibevoice)
    assert resolved == mlx_dir
    assert weights_present("moss_hf", mlx_dir)
