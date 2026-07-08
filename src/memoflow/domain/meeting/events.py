"""会议（Meeting）上下文 —— 领域事件。"""
from __future__ import annotations

from memoflow.domain.shared.entity import DomainEvent


class MeetingUploaded(DomainEvent):
    def __init__(self, meeting_id: str) -> None:
        super().__init__()
        self.meeting_id = meeting_id


class MeetingTranscribed(DomainEvent):
    def __init__(self, meeting_id: str, transcript_id: str) -> None:
        super().__init__()
        self.meeting_id = meeting_id
        self.transcript_id = transcript_id


class MeetingDiarized(DomainEvent):
    def __init__(self, meeting_id: str, transcript_id: str) -> None:
        super().__init__()
        self.meeting_id = meeting_id
        self.transcript_id = transcript_id


class MeetingSummarized(DomainEvent):
    def __init__(self, meeting_id: str, summary_id: str) -> None:
        super().__init__()
        self.meeting_id = meeting_id
        self.summary_id = summary_id


class MeetingFailed(DomainEvent):
    def __init__(self, meeting_id: str, stage: str, reason: str) -> None:
        super().__init__()
        self.meeting_id = meeting_id
        self.stage = stage
        self.reason = reason
