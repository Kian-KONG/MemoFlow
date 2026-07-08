"""端到端集成测试：使用假的 AI 适配器（不加载真实模型）驱动完整的会议处理流水线。

验证 DDD 分层之间的协作是否正确：应用服务 -> 领域聚合 -> 仓储持久化 -> 向量库索引。
"""
from __future__ import annotations

import json

import pytest

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.application.meeting_service import MeetingApplicationService
from memoflow.application.pipeline.processing_pipeline import MeetingProcessingPipeline
from memoflow.application.ports.asr_port import ASRPort, ASRResult, ASRSegment
from memoflow.application.ports.diarization_port import DiarizationPort, SpeakerSegment
from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.application.ports.llm_port import LLMPort
from memoflow.application.pipeline.runner import AsyncioPipelineRunner
from memoflow.application.summary_service import SummaryApplicationService
from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.application.system_service import ModelService
from memoflow.domain.meeting.value_objects import MeetingStatus
from memoflow.domain.shared.events import EventDispatcher
from memoflow.infrastructure.persistence.db import create_engine, create_session_factory, init_models
from memoflow.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from memoflow.infrastructure.storage.file_storage import LocalFileStorage
from memoflow.infrastructure.vectorstore.lancedb_repository import LanceDBVectorRepository


class FakeASR(ASRPort):
    call_count = 0

    async def transcribe(self, audio_path: str) -> ASRResult:
        FakeASR.call_count += 1
        return ASRResult(
            language="zh",
            segments=[
                ASRSegment(start=0.0, end=2.0, text="大家好，我们开始今天的周会"),
                ASRSegment(start=2.5, end=5.0, text="这周进度基本符合预期"),
            ],
        )


class FakeDiarization(DiarizationPort):
    async def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        return [
            SpeakerSegment(start=0.0, end=2.2, speaker_label="SPEAKER_00"),
            SpeakerSegment(start=2.2, end=6.0, speaker_label="SPEAKER_01"),
        ]


class FakeLLM(LLMPort):
    async def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=None) -> str:  # noqa: ANN001
        return json.dumps(
            {
                "overview": "本次周会同步了项目进度，整体符合预期。",
                "key_points": ["进度正常", "无重大风险"],
                "decisions": ["继续按原计划推进"],
                "action_items": [{"description": "补充单元测试", "owner": "张三"}],
            },
            ensure_ascii=False,
        )


class FakeEmbedding(EmbeddingPort):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 5), 0.1, 0.2] for t in texts]

    @property
    def dimension(self) -> int:
        return 3


class _BypassModelService(ModelService):
    """集成测试用：跳过真实模型预检。"""

    def ensure_processing_models_ready(self) -> None:
        return

    def get_missing_for_processing(self) -> list[str]:
        return []


@pytest.fixture()
async def pipeline_context(tmp_path):
    FakeASR.call_count = 0
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await init_models(engine)
    session_factory = create_session_factory(engine)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    file_storage = LocalFileStorage(tmp_path / "audio")
    vector_repository = LanceDBVectorRepository(str(tmp_path / "lancedb"))

    transcription_service = TranscriptionApplicationService(
        uow_factory, file_storage, FakeASR(), FakeDiarization()
    )
    summary_service = SummaryApplicationService(uow_factory, FakeLLM(), llm_model_name="fake-llm")
    knowledge_service = KnowledgeApplicationService(uow_factory, FakeEmbedding(), vector_repository)

    from memoflow.config import get_settings

    model_service = _BypassModelService(
        get_settings(), FakeASR(), FakeDiarization(), FakeLLM(), FakeEmbedding()
    )

    pipeline = MeetingProcessingPipeline(
        uow_factory, transcription_service, summary_service, knowledge_service, model_service
    )
    pipeline_runner = AsyncioPipelineRunner(pipeline)
    meeting_service = MeetingApplicationService(
        uow_factory, file_storage, EventDispatcher(), pipeline_runner
    )

    yield meeting_service, transcription_service, summary_service, knowledge_service, uow_factory
    await engine.dispose()


async def test_full_pipeline_completes_meeting(pipeline_context):
    meeting_service, transcription_service, summary_service, knowledge_service, _ = pipeline_context

    meeting = await meeting_service.upload_meeting(
        title="周会 0708",
        filename="meeting.wav",
        content_type="audio/wav",
        content=b"fake-audio-bytes",
    )

    import asyncio

    for _ in range(50):
        await asyncio.sleep(0.05)
        meeting = await meeting_service.get_meeting(meeting.id)
        if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.FAILED):
            break

    assert meeting.status == MeetingStatus.COMPLETED, meeting.error_message

    transcript = await transcription_service.get_transcript(meeting.id)
    assert len(transcript.utterances) == 2
    assert transcript.utterances[0].speaker.label == "SPEAKER_00"

    summary = await summary_service.get_summary(meeting.id)
    assert summary.overview
    assert len(summary.action_items) == 1
    assert summary.action_items[0].owner == "张三"

    hits = await knowledge_service.search(query="进度", meeting_id=meeting.id, top_k=3)
    assert len(hits) >= 1


async def test_retry_resumes_from_diarization_without_rerunning_asr(pipeline_context):
    import asyncio

    from memoflow.domain.meeting.value_objects import MeetingId

    meeting_service, _, _, _, uow_factory = pipeline_context

    meeting = await meeting_service.upload_meeting(
        title="断点续跑测试",
        filename="meeting.wav",
        content_type="audio/wav",
        content=b"fake-audio-bytes",
    )

    for _ in range(50):
        await asyncio.sleep(0.05)
        meeting = await meeting_service.get_meeting(meeting.id)
        if meeting.status in (MeetingStatus.COMPLETED, MeetingStatus.FAILED):
            break

    assert meeting.status == MeetingStatus.COMPLETED, meeting.error_message
    asr_calls_after_first_run = FakeASR.call_count
    assert asr_calls_after_first_run == 1

    async with uow_factory() as uow:
        m = await uow.meetings.get(MeetingId(meeting.id))
        assert m is not None
        m.status = MeetingStatus.DIARIZING
        m.summary_id = None
        m.fail(stage="diarization", reason="simulated pyannote failure")
        await uow.meetings.save(m)
        await uow.commit()

    retried = await meeting_service.retry_meeting(meeting.id)
    assert retried.status == MeetingStatus.DIARIZING
    assert retried.transcript_id is not None

    for _ in range(50):
        await asyncio.sleep(0.05)
        retried = await meeting_service.get_meeting(meeting.id)
        if retried.status in (MeetingStatus.COMPLETED, MeetingStatus.FAILED):
            break

    assert retried.status == MeetingStatus.COMPLETED, retried.error_message
    assert FakeASR.call_count == asr_calls_after_first_run
