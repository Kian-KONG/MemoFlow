import platform

from memoflow.infrastructure.ai.asr_defaults import default_asr_backend


def test_default_asr_backend_darwin_arm_uses_moss_hf(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert default_asr_backend() == "moss_hf"


def test_default_asr_backend_non_darwin_uses_vibevoice(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert default_asr_backend() == "vibevoice"
