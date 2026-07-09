"""Meeting 聚合根的单元测试：状态机迁移与不变量校验。"""
from __future__ import annotations

import pytest

from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.events import MeetingFailed, MeetingSummarized, MeetingUploaded
from memoflow.domain.meeting.services import AudioValidationPolicy
from memoflow.domain.meeting.value_objects import AudioFile, MeetingStatus
from memoflow.domain.shared.exceptions import InvalidStateTransitionError, InvariantViolationError


def _make_audio(**overrides) -> AudioFile:
    defaults = dict(
        storage_path="abc.wav",
        original_filename="abc.wav",
        content_type="audio/wav",
        size_bytes=1024,
    )
    defaults.update(overrides)
    return AudioFile(**defaults)


def test_upload_creates_meeting_with_uploaded_status_and_event():
    meeting = Meeting.upload(title="周会", audio=_make_audio())

    assert meeting.status == MeetingStatus.UPLOADED
    events = meeting.pull_events()
    assert len(events) == 1
    assert isinstance(events[0], MeetingUploaded)
    # pull_events 后应清空
    assert meeting.pull_events() == []


def test_full_happy_path_transitions_to_completed():
    meeting = Meeting.upload(title="周会", audio=_make_audio())
    meeting.pull_events()

    meeting.start_transcribing()
    assert meeting.status == MeetingStatus.TRANSCRIBING

    meeting.complete_transcription(transcript_id="t-1")
    assert meeting.status == MeetingStatus.DIARIZING
    assert meeting.transcript_id == "t-1"

    meeting.complete_diarization()
    assert meeting.status == MeetingStatus.SUMMARIZING

    meeting.complete_summarization(summary_id="s-1")
    assert meeting.status == MeetingStatus.COMPLETED
    assert meeting.summary_id == "s-1"

    events = meeting.pull_events()
    assert any(isinstance(e, MeetingSummarized) for e in events)


def test_invalid_transition_raises():
    meeting = Meeting.upload(title="周会", audio=_make_audio())
    with pytest.raises(InvalidStateTransitionError):
        meeting.complete_summarization(summary_id="s-1")  # 尚未转写就想生成摘要


def test_fail_and_retry_resumes_from_failed_stage():
    meeting = Meeting.upload(title="周会", audio=_make_audio())
    meeting.start_transcribing()
    meeting.complete_transcription(transcript_id="t-1")
    meeting.fail(stage="diarization", reason="模型加载失败")

    assert meeting.status == MeetingStatus.FAILED
    assert meeting.error_message == "模型加载失败"
    assert meeting.failed_stage == "diarization"
    assert meeting.resume_status == "diarizing"
    assert meeting.transcript_id == "t-1"
    assert any(isinstance(e, MeetingFailed) for e in meeting.pull_events())

    meeting.retry()
    assert meeting.status == MeetingStatus.DIARIZING
    assert meeting.error_message is None
    assert meeting.transcript_id == "t-1"


def test_ensure_transcribing_is_idempotent_when_already_transcribing():
    meeting = Meeting.upload(title="周会", audio=_make_audio())
    meeting.start_transcribing()
    meeting.ensure_transcribing()
    assert meeting.status == MeetingStatus.TRANSCRIBING


def test_empty_title_raises_invariant_violation():
    with pytest.raises(InvariantViolationError):
        Meeting.upload(title="   ", audio=_make_audio())


def test_audio_validation_rejects_unsupported_content_type():
    audio = _make_audio(content_type="video/mp4")
    with pytest.raises(InvariantViolationError):
        AudioValidationPolicy.validate(audio)


def test_audio_validation_accepts_wav():
    audio = _make_audio(content_type="audio/wav")
    AudioValidationPolicy.validate(audio)  # 不应抛出异常


def test_normalize_content_type_from_m4a_extension():
    normalized = AudioValidationPolicy.normalize_content_type("application/octet-stream", "meeting.m4a")
    assert normalized == "audio/mp4"
    audio = _make_audio(content_type=normalized, original_filename="meeting.m4a")
    AudioValidationPolicy.validate(audio)
