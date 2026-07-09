"""转写（Transcript）仓储端口。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from memoflow.domain.transcript.entities import Transcript
from memoflow.domain.transcript.value_objects import TranscriptId


class TranscriptRepository(ABC):
    @abstractmethod
    async def add(self, transcript: Transcript) -> None: ...

    @abstractmethod
    async def get(self, transcript_id: TranscriptId) -> Transcript | None: ...

    @abstractmethod
    async def get_by_meeting_id(self, meeting_id: str) -> Transcript | None: ...

    @abstractmethod
    async def save(self, transcript: Transcript) -> None: ...

    @abstractmethod
    async def delete_by_meeting_id(self, meeting_id: str) -> None: ...
