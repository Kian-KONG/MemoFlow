"""会议应用服务（Meeting Application Service）。

负责编排"上传会议 -> 触发处理流水线 -> 查询会议"等用例，
是接口层（API/UI）与领域层之间的唯一入口（Service Layer 模式）。
"""
from __future__ import annotations

from loguru import logger

from memoflow.application.dto import MeetingDTO
from memoflow.application.ports.file_storage_port import FileStoragePort
from memoflow.application.ports.pipeline_runner import PipelineRunner
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.domain.meeting.entities import Meeting
from memoflow.domain.meeting.services import AudioValidationPolicy
from memoflow.domain.meeting.value_objects import AudioFile, MeetingId, MeetingStatus
from memoflow.domain.shared.entity import DomainEvent
from memoflow.domain.shared.events import EventDispatcher
from memoflow.domain.shared.exceptions import EntityNotFoundError


class MeetingApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        file_storage: FileStoragePort,
        event_dispatcher: EventDispatcher,
        pipeline_runner: PipelineRunner,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_storage = file_storage
        self._event_dispatcher = event_dispatcher
        self._pipeline_runner = pipeline_runner

    async def upload_meeting(
        self, title: str, filename: str, content_type: str, content: bytes
    ) -> MeetingDTO:
        """上传一段会议录音：保存文件、创建 Meeting 聚合、异步触发处理流水线。"""
        storage_path = await self._file_storage.save(filename, content)
        normalized_type = AudioValidationPolicy.normalize_content_type(content_type, filename)
        audio = AudioFile(
            storage_path=storage_path,
            original_filename=filename,
            content_type=normalized_type,
            size_bytes=len(content),
        )
        AudioValidationPolicy.validate(audio)

        meeting = Meeting.upload(title=title or filename, audio=audio)

        async with self._uow_factory() as uow:
            await uow.meetings.add(meeting)
            await uow.commit()

        await self._publish_events(meeting)
        logger.info(f"会议已上传: id={meeting.id} title={meeting.title}")

        await self._pipeline_runner.schedule(str(meeting.id))
        return MeetingDTO.from_domain(meeting)

    async def get_meeting(self, meeting_id: str) -> MeetingDTO:
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
        if meeting is None:
            raise EntityNotFoundError("Meeting", meeting_id)
        return MeetingDTO.from_domain(meeting)

    async def list_meetings(
        self, status: MeetingStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[MeetingDTO]:
        async with self._uow_factory() as uow:
            meetings = await uow.meetings.list_all(status=status, limit=limit, offset=offset)
        return [MeetingDTO.from_domain(m) for m in meetings]

    async def retry_meeting(self, meeting_id: str) -> MeetingDTO:
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            meeting.retry()
            await uow.meetings.save(meeting)
            await uow.commit()

        await self._pipeline_runner.schedule(meeting_id)
        return MeetingDTO.from_domain(meeting)

    async def _publish_events(self, meeting: Meeting) -> None:
        events: list[DomainEvent] = meeting.pull_events()
        await self._event_dispatcher.publish_all(events)
