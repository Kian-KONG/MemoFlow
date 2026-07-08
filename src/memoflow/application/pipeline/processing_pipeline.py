"""会议处理流水线：串联转写 -> 摘要 -> 知识库索引，并负责失败状态的记录。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.application.summary_service import SummaryApplicationService
from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.domain.meeting.value_objects import MeetingId


class MeetingProcessingPipeline:
    """编排一次会议从上传到完成的全部处理阶段。

    每个阶段都是独立可替换的应用服务，流水线本身只负责顺序编排与异常处理，
    任意阶段失败都会将 Meeting 标记为 FAILED 并记录失败原因，不会影响已完成的阶段数据。
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        transcription_service: TranscriptionApplicationService,
        summary_service: SummaryApplicationService,
        knowledge_service: KnowledgeApplicationService,
    ) -> None:
        self._uow_factory = uow_factory
        self._transcription_service = transcription_service
        self._summary_service = summary_service
        self._knowledge_service = knowledge_service

    async def run(self, meeting_id: str) -> None:
        stage = "transcription"
        try:
            logger.info(f"[{meeting_id}] 流水线启动")
            stage = "transcription"
            await self._transcription_service.transcribe_meeting(meeting_id)

            stage = "summarization"
            await self._summary_service.summarize_meeting(meeting_id)

            stage = "knowledge_indexing"
            await self._knowledge_service.index_meeting(meeting_id)

            logger.info(f"[{meeting_id}] 流水线全部完成")
        except Exception as exc:  # noqa: BLE001 - 流水线顶层需要兜底捕获，避免后台任务静默失败
            logger.exception(f"[{meeting_id}] 流水线在阶段 [{stage}] 失败: {exc}")
            await self._mark_failed(meeting_id, stage, str(exc))

    async def _mark_failed(self, meeting_id: str, stage: str, reason: str) -> None:
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                return
            meeting.fail(stage=stage, reason=reason)
            await uow.meetings.save(meeting)
            await uow.commit()
