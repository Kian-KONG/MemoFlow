import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _load_download_module():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "scripts" / "download_modelscope_model.py"
    spec = importlib.util.spec_from_file_location("download_modelscope_model", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ms_module():
    return _load_download_module()


def test_human_bytes_formats_sizes(ms_module):
    assert ms_module.human_bytes(512) == "512B"
    assert ms_module.human_bytes(2048).endswith("KB")


def test_analyze_repo_compares_local_sizes(ms_module, tmp_path: Path, monkeypatch):
    local_dir = tmp_path / "model"
    local_dir.mkdir()
    complete_file = local_dir / "config.json"
    complete_file.write_bytes(b"x" * 10)
    (local_dir / "weights.bin").write_bytes(b"x" * 3)

    class FakeHubApi:
        def get_model_files(self, model_id, revision=None, recursive=True):
            return [
                {"Path": "config.json", "Size": 10},
                {"Path": "weights.bin", "Size": 8},
                {"Path": ".gitignore", "Size": 1},
            ]

    fake_api = types.SimpleNamespace(HubApi=FakeHubApi)
    monkeypatch.setitem(sys.modules, "modelscope", types.ModuleType("modelscope"))
    monkeypatch.setitem(sys.modules, "modelscope.hub", types.ModuleType("modelscope.hub"))
    monkeypatch.setitem(sys.modules, "modelscope.hub.api", fake_api)
    monkeypatch.setattr(
        ms_module,
        "list_remote_files",
        lambda _model_id: FakeHubApi().get_model_files("OpenMOSS/MOSS"),
    )

    pending, complete, have, need = ms_module.analyze_repo("OpenMOSS/MOSS", local_dir)

    assert complete == [("config.json", 10)]
    assert pending == [("weights.bin", 8)]
    assert have == 10
    assert need == 18


def test_marker_files_complete_detects_key_files(ms_module, tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert ms_module.marker_files_complete("any/repo", empty_dir) is False

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    assert ms_module.marker_files_complete("any/repo", model_dir) is True


def test_check_only_returns_zero_when_complete(ms_module, tmp_path: Path, monkeypatch, capsys):
    local_dir = tmp_path / "model"
    local_dir.mkdir()

    monkeypatch.setattr(
        ms_module,
        "analyze_repo",
        lambda *_args, **_kwargs: ([], [("config.json", 10)], 10, 10),
    )
    monkeypatch.setattr(sys, "argv", ["prog", "OpenMOSS/MOSS", "--local-dir", str(local_dir), "--check-only"])

    assert ms_module.main() == 0
    assert "所有文件已完整" in capsys.readouterr().out


def test_check_only_returns_two_when_pending(ms_module, tmp_path: Path, monkeypatch, capsys):
    local_dir = tmp_path / "model"
    local_dir.mkdir()

    monkeypatch.setattr(
        ms_module,
        "analyze_repo",
        lambda *_args, **_kwargs: ([("weights.bin", 8)], [], 0, 8),
    )
    monkeypatch.setattr(sys, "argv", ["prog", "OpenMOSS/MOSS", "--local-dir", str(local_dir), "--check-only"])

    assert ms_module.main() == 2
    assert "[--check-only]" in capsys.readouterr().out


def test_check_only_falls_back_to_markers_when_api_fails(ms_module, tmp_path: Path, monkeypatch, capsys):
    local_dir = tmp_path / "model"
    local_dir.mkdir()
    (local_dir / "config.json").write_text("{}", encoding="utf-8")
    (local_dir / "model.safetensors").write_bytes(b"x")

    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(ms_module, "analyze_repo", boom)
    monkeypatch.setattr(sys, "argv", ["prog", "OpenMOSS/MOSS", "--local-dir", str(local_dir), "--check-only"])

    assert ms_module.main() == 0
    out = capsys.readouterr().out
    assert "关键 marker 文件" in out
