"""领域实体 <-> ORM 模型 映射函数。"""
from __future__ import annotations

from datetime import datetime, timezone

from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.value_objects import AudioFile, MeetingId, MeetingStatus
from memoflow.domain.summary.entities import ActionItem, Decision, Summary
from memoflow.domain.summary.value_objects import ActionItemId, ActionItemStatus, DecisionId, SummaryId
from memoflow.domain.shared.value_objects import TimeRange
from memoflow.domain.transcript.entities import Speaker, Transcript, Utterance
from memoflow.domain.transcript.value_objects import SpeakerId, TranscriptId, UtteranceId
from memoflow.infrastructure.persistence.models import (
    ActionItemModel,
    DecisionModel,
    MeetingModel,
    SpeakerModel,
    SummaryModel,
    TranscriptModel,
    UtteranceModel,
)


def _as_utc(dt: datetime) -> datetime:
    """SQLite 读回的 naive datetime 视为 UTC。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Meeting
# ---------------------------------------------------------------------------


def meeting_to_domain(model: MeetingModel) -> Meeting:
    audio = AudioFile(
        storage_path=model.storage_path,
        original_filename=model.original_filename,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        duration_seconds=model.duration_seconds,
    )
    return Meeting(
        meeting_id=MeetingId(model.id),
        title=model.title,
        audio=audio,
        status=MeetingStatus(model.status),
        created_at=_as_utc(model.created_at),
        updated_at=_as_utc(model.updated_at),
        transcript_id=model.transcript_id,
        summary_id=model.summary_id,
        error_message=model.error_message,
        failed_stage=model.failed_stage,
        resume_status=model.resume_status,
    )


def meeting_to_model(meeting: Meeting) -> MeetingModel:
    return MeetingModel(
        id=str(meeting.id),
        title=meeting.title,
        status=meeting.status.value,
        storage_path=meeting.audio.storage_path,
        original_filename=meeting.audio.original_filename,
        content_type=meeting.audio.content_type,
        size_bytes=meeting.audio.size_bytes,
        duration_seconds=meeting.audio.duration_seconds,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        transcript_id=meeting.transcript_id,
        summary_id=meeting.summary_id,
        error_message=meeting.error_message,
        failed_stage=meeting.failed_stage,
        resume_status=meeting.resume_status,
    )


def apply_meeting_to_model(meeting: Meeting, model: MeetingModel) -> None:
    """将聚合根的最新状态写回既有 ORM 实例（用于 update）。"""
    model.title = meeting.title
    model.status = meeting.status.value
    model.duration_seconds = meeting.audio.duration_seconds
    model.updated_at = meeting.updated_at
    model.transcript_id = meeting.transcript_id
    model.summary_id = meeting.summary_id
    model.error_message = meeting.error_message
    model.failed_stage = meeting.failed_stage
    model.resume_status = meeting.resume_status


# ---------------------------------------------------------------------------
# Transcript
# ---------------------------------------------------------------------------


def transcript_to_domain(model: TranscriptModel) -> Transcript:
    speakers: dict[SpeakerId, Speaker] = {}
    for speaker_model in model.speakers:
        speaker_id = SpeakerId(speaker_model.id)
        speakers[speaker_id] = Speaker(
            speaker_id=speaker_id, label=speaker_model.label, display_name=speaker_model.display_name
        )

    utterances = [
        Utterance(
            utterance_id=UtteranceId(u.id),
            time_range=TimeRange(u.start, u.end),
            text=u.text,
            speaker_id=SpeakerId(u.speaker_id) if u.speaker_id else None,
            confidence=u.confidence,
        )
        for u in sorted(model.utterances, key=lambda u: u.start)
    ]

    return Transcript(
        transcript_id=TranscriptId(model.id),
        meeting_id=model.meeting_id,
        language=model.language,
        utterances=utterances,
        speakers=speakers,
        created_at=model.created_at,
    )


def transcript_to_model(transcript: Transcript) -> TranscriptModel:
    return TranscriptModel(
        id=str(transcript.id),
        meeting_id=transcript.meeting_id,
        language=transcript.language,
        created_at=transcript.created_at,
        speakers=[
            SpeakerModel(id=str(s.id), label=s.label, display_name=s.display_name)
            for s in transcript.speakers.values()
        ],
        utterances=[
            UtteranceModel(
                id=str(u.id),
                speaker_id=str(u.speaker_id) if u.speaker_id else None,
                start=u.time_range.start,
                end=u.time_range.end,
                text=u.text,
                confidence=u.confidence,
            )
            for u in transcript.utterances
        ],
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summary_to_domain(model: SummaryModel) -> Summary:
    decisions = [
        Decision(
            decision_id=DecisionId(d.id),
            description=d.description,
            related_utterance_ids=list(d.related_utterance_ids),
        )
        for d in model.decisions
    ]
    action_items = [
        ActionItem(
            action_item_id=ActionItemId(a.id),
            description=a.description,
            owner=a.owner,
            due_date=a.due_date,
            status=ActionItemStatus(a.status),
            related_utterance_ids=list(a.related_utterance_ids),
        )
        for a in model.action_items
    ]
    return Summary(
        summary_id=SummaryId(model.id),
        meeting_id=model.meeting_id,
        overview=model.overview,
        key_points=list(model.key_points),
        decisions=decisions,
        action_items=action_items,
        generated_by_model=model.generated_by_model,
        generated_at=model.generated_at,
    )


def summary_to_model(summary: Summary) -> SummaryModel:
    return SummaryModel(
        id=str(summary.id),
        meeting_id=summary.meeting_id,
        overview=summary.overview,
        key_points=list(summary.key_points),
        generated_by_model=summary.generated_by_model,
        generated_at=summary.generated_at,
        decisions=[
            DecisionModel(
                id=str(d.id), description=d.description, related_utterance_ids=d.related_utterance_ids
            )
            for d in summary.decisions
        ],
        action_items=[
            ActionItemModel(
                id=str(a.id),
                description=a.description,
                owner=a.owner,
                due_date=a.due_date,
                status=a.status.value,
                related_utterance_ids=a.related_utterance_ids,
            )
            for a in summary.action_items
        ],
    )
