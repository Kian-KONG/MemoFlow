"""运行时偏好持久化测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from memoflow.infrastructure.config.runtime_preferences import RuntimePreferences


def test_load_empty_when_missing(tmp_path: Path) -> None:
    prefs = RuntimePreferences.load(tmp_path)
    assert prefs.asr_backend is None


def test_save_and_load_asr_backend(tmp_path: Path) -> None:
    prefs = RuntimePreferences(data_dir=tmp_path)
    prefs.save_asr_backend("moss_hf")
    loaded = RuntimePreferences.load(tmp_path)
    assert loaded.asr_backend == "moss_hf"


def test_save_rejects_unknown_backend(tmp_path: Path) -> None:
    prefs = RuntimePreferences(data_dir=tmp_path)
    with pytest.raises(ValueError, match="未知"):
        prefs.save_asr_backend("unknown")


def test_clear_asr_backend(tmp_path: Path) -> None:
    prefs = RuntimePreferences(data_dir=tmp_path)
    prefs.save_asr_backend("vibevoice")
    prefs.clear_asr_backend()
    assert prefs.asr_backend is None
    assert not prefs.path.is_file()
