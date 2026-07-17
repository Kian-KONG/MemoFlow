"""MossHFASR 应通过 ModelRunner 公共 API 触发加载。"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

from memoflow.infrastructure.ai.moss_hf_asr import MossHFASR


def test_load_from_local_uses_public_ensure_loaded(tmp_path: Path) -> None:
    model_dir = tmp_path / "MOSS-Transcribe-Diarize"
    model_dir.mkdir()
    (model_dir / "configuration_moss_transcribe_diarize.py").write_text("# stub\n", encoding="utf-8")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"x" * 128)

    runner = MagicMock()
    runner.is_loaded = False

    model_runner_mod = types.ModuleType("moss_transcribe_diarize.app.model_runner")
    model_runner_mod.ModelRunner = MagicMock(return_value=runner)
    app_mod = types.ModuleType("moss_transcribe_diarize.app")
    pkg = types.ModuleType("moss_transcribe_diarize")

    asr = MossHFASR(model_path=model_dir, device="cpu")
    with patch.dict(
        sys.modules,
        {
            "moss_transcribe_diarize": pkg,
            "moss_transcribe_diarize.app": app_mod,
            "moss_transcribe_diarize.app.model_runner": model_runner_mod,
        },
    ):
        asr._load_from_local(None)

    model_runner_mod.ModelRunner.assert_called_once()
    runner.ensure_loaded.assert_called_once_with()
    assert asr._runner is runner
