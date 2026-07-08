"""应用层 DTO（数据传输对象）。

用于在应用服务与接口层（API / UI）之间传递数据，避免接口层直接依赖领域实体，
从而让领域模型可以自由演进而不破坏外部契约。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.value_objects import MeetingStatus
from memoflow.domain.summary.entities import Summary
from memoflow.domain.summary.value_objects import ActionItemStatus
from memoflow.domain.transcript.entities import Transcript


@dataclass(frozen=True)
class MeetingDTO:
    id: str
    title: str
    status: MeetingStatus
    original_filename: str
    duration_seconds: float | None
    created_at: datetime
    updated_at: datetime
    transcript_id: str | None
    summary_id: str | None
    error_message: str | None

    @staticmethod
    def from_domain(meeting: Meeting) -> "MeetingDTO":
        return MeetingDTO(
            id=str(meeting.id),
            title=meeting.title,
            status=meeting.status,
            original_filename=meeting.audio.original_filename,
            duration_seconds=meeting.audio.duration_seconds,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            transcript_id=meeting.transcript_id,
            summary_id=meeting.summary_id,
            error_message=meeting.error_message,
        )


@dataclass(frozen=True)
class SpeakerDTO:
    id: str
    label: str
    display_name: str | None


@dataclass(frozen=True)
class UtteranceDTO:
    id: str
    start: float
    end: float
    text: str
    speaker: SpeakerDTO | None
    confidence: float | None


@dataclass(frozen=True)
class TranscriptDTO:
    id: str
    meeting_id: str
    language: str
    utterances: list[UtteranceDTO]
    speakers: list[SpeakerDTO]

    @staticmethod
    def from_domain(transcript: Transcript) -> "TranscriptDTO":
        speaker_dtos = {
            sid: SpeakerDTO(id=str(sid), label=s.label, display_name=s.display_name)
            for sid, s in transcript.speakers.items()
        }
        utterances = [
            UtteranceDTO(
                id=str(u.id),
                start=u.time_range.start,
                end=u.time_range.end,
                text=u.text,
                speaker=speaker_dtos.get(u.speaker_id) if u.speaker_id else None,
                confidence=u.confidence,
            )
            for u in transcript.utterances
        ]
        return TranscriptDTO(
            id=str(transcript.id),
            meeting_id=transcript.meeting_id,
            language=transcript.language,
            utterances=utterances,
            speakers=list(speaker_dtos.values()),
        )


@dataclass(frozen=True)
class DecisionDTO:
    id: str
    description: str
    related_utterance_ids: list[str]


@dataclass(frozen=True)
class ActionItemDTO:
    id: str
    description: str
    owner: str | None
    due_date: date | None
    status: ActionItemStatus
    related_utterance_ids: list[str]


@dataclass(frozen=True)
class SummaryDTO:
    id: str
    meeting_id: str
    overview: str
    key_points: list[str]
    decisions: list[DecisionDTO]
    action_items: list[ActionItemDTO]
    generated_by_model: str
    generated_at: datetime

    @staticmethod
    def from_domain(summary: Summary) -> "SummaryDTO":
        return SummaryDTO(
            id=str(summary.id),
            meeting_id=summary.meeting_id,
            overview=summary.overview,
            key_points=list(summary.key_points),
            decisions=[
                DecisionDTO(id=str(d.id), description=d.description, related_utterance_ids=d.related_utterance_ids)
                for d in summary.decisions
            ],
            action_items=[
                ActionItemDTO(
                    id=str(a.id),
                    description=a.description,
                    owner=a.owner,
                    due_date=a.due_date,
                    status=a.status,
                    related_utterance_ids=a.related_utterance_ids,
                )
                for a in summary.action_items
            ],
            generated_by_model=summary.generated_by_model,
            generated_at=summary.generated_at,
        )


@dataclass(frozen=True)
class KnowledgeHitDTO:
    chunk_id: str
    meeting_id: str
    text: str
    score: float
    source_utterance_ids: list[str] = field(default_factory=list)
