"""ASR 后端热切换测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.application.system_service import ModelService
from memoflow.config import Settings
from memoflow.container import AppContainer
from memoflow.infrastructure.config.runtime_preferences import RuntimePreferences


class _FakeASR(ASRPort):
    def __init__(self, backend: str, ready: bool = True) -> None:
        self._backend_key = backend  # type: ignore[attr-defined]
        self._ready = ready
        self._loaded = False

    @property
    def source(self) -> str:
        return "test"

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    async def transcribe(self, audio_path: str) -> ASRResult:
        return ASRResult(language="zh", segments=[ASRSegment(start=0, end=1, text="hi")])


def _minimal_settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        lancedb_dir=tmp_path / "lancedb",
        audio_dir=tmp_path / "audio",
        asr_backend="vibevoice",
    )


def test_switch_asr_backend_updates_services(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    runtime_prefs = RuntimePreferences(data_dir=tmp_path)
    asr = _FakeASR("vibevoice")
    transcription = MagicMock()
    transcription.set_asr = MagicMock()
    system_service = ModelService(settings, asr, runtime_prefs=runtime_prefs)
    system_service.set_asr = MagicMock(wraps=system_service.set_asr)

    container = AppContainer(
        settings=settings,
        engine=MagicMock(),
        uow_factory=MagicMock(),
        event_dispatcher=MagicMock(),
        file_storage=MagicMock(),
        asr=asr,
        llm=MagicMock(),
        embedding=MagicMock(),
        reranker=MagicMock(),
        vector_repository=MagicMock(),
        meeting_service=MagicMock(),
        transcription_service=transcription,
        summary_service=MagicMock(),
        knowledge_service=MagicMock(),
        system_service=system_service,
        pipeline=MagicMock(),
        pipeline_runner=MagicMock(),
        runtime_prefs=runtime_prefs,
    )

    new_asr = _FakeASR("moss_hf")

    with (
        patch("memoflow.container.weights_present", return_value=True),
        patch("memoflow.container.resolve_model_path", return_value=tmp_path / "models" / "MOSS"),
        patch("memoflow.container.build_asr_for_backend", return_value=new_asr),
    ):
        active = container.switch_asr_backend("moss_hf")

    assert active == "moss_hf"
    assert container.asr is new_asr
    transcription.set_asr.assert_called_once_with(new_asr)
    assert runtime_prefs.asr_backend == "moss_hf"
