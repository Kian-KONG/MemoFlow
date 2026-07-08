"""会议（Meeting）聚合根。"""
from __future__ import annotations

from datetime import datetime

from memoflow.domain.meeting.events import (
    MeetingDiarized,
    MeetingFailed,
    MeetingSummarized,
    MeetingTranscribed,
    MeetingUploaded,
)
from memoflow.domain.meeting.value_objects import (
    ALLOWED_TRANSITIONS,
    AudioFile,
    MeetingId,
    MeetingStatus,
)
from memoflow.domain.shared.entity import AggregateRoot, utcnow
from memoflow.domain.shared.exceptions import InvalidStateTransitionError, InvariantViolationError


class Meeting(AggregateRoot[MeetingId]):
    """会议聚合根：管理一次会议录音从上传到生成摘要的完整生命周期与状态机。"""

    def __init__(
        self,
        meeting_id: MeetingId,
        title: str,
        audio: AudioFile,
        status: MeetingStatus,
        created_at: datetime,
        updated_at: datetime,
        transcript_id: str | None = None,
        summary_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        super().__init__(meeting_id)
        if not title.strip():
            raise InvariantViolationError("会议标题不能为空")
        self.title = title
        self.audio = audio
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.transcript_id = transcript_id
        self.summary_id = summary_id
        self.error_message = error_message

    # ---- 工厂方法 ----
    @classmethod
    def upload(cls, title: str, audio: AudioFile) -> "Meeting":
        now = utcnow()
        meeting = cls(
            meeting_id=MeetingId.new(),
            title=title,
            audio=audio,
            status=MeetingStatus.UPLOADED,
            created_at=now,
            updated_at=now,
        )
        meeting.record_event(MeetingUploaded(str(meeting.id)))
        return meeting

    # ---- 状态机迁移 ----
    def _transition(self, target: MeetingStatus) -> None:
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStateTransitionError("Meeting", self.status.value, f"-> {target.value}")
        self.status = target
        self.updated_at = utcnow()

    def start_transcribing(self) -> None:
        self._transition(MeetingStatus.TRANSCRIBING)

    def complete_transcription(self, transcript_id: str) -> None:
        self.transcript_id = transcript_id
        self._transition(MeetingStatus.DIARIZING)
        self.record_event(MeetingTranscribed(str(self.id), transcript_id))

    def complete_diarization(self) -> None:
        if self.transcript_id is None:
            raise InvariantViolationError("必须先完成转写才能进行说话人识别")
        self._transition(MeetingStatus.SUMMARIZING)
        self.record_event(MeetingDiarized(str(self.id), self.transcript_id))

    def complete_summarization(self, summary_id: str) -> None:
        self.summary_id = summary_id
        self._transition(MeetingStatus.COMPLETED)
        self.record_event(MeetingSummarized(str(self.id), summary_id))

    def fail(self, stage: str, reason: str) -> None:
        self.status = MeetingStatus.FAILED
        self.error_message = reason
        self.updated_at = utcnow()
        self.record_event(MeetingFailed(str(self.id), stage, reason))

    def retry(self) -> None:
        if self.status != MeetingStatus.FAILED:
            raise InvalidStateTransitionError("Meeting", self.status.value, "retry")
        self.error_message = None
        self._transition(MeetingStatus.TRANSCRIBING)

    def rename(self, new_title: str) -> None:
        if not new_title.strip():
            raise InvariantViolationError("会议标题不能为空")
        self.title = new_title
        self.updated_at = utcnow()
