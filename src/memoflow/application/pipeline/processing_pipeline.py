"""会议处理流水线：串联转写 -> 摘要 -> 知识库索引，并负责失败状态的记录。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.application.summary_service import SummaryApplicationService
from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.application.system_service import ModelNotReadyError, ModelService
from memoflow.domain.meeting.value_objects import MeetingId, MeetingStatus


class MeetingProcessingPipeline:
    """编排一次会议从上传到完成的全部处理阶段。

    每个阶段都是独立可替换的应用服务，流水线本身只负责顺序编排与异常处理，
    任意阶段失败都会将 Meeting 标记为 FAILED 并记录失败原因，不会影响已完成的阶段数据。
    重试时根据各阶段缓存产物从最近失败点继续，而非从头开始。
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        transcription_service: TranscriptionApplicationService,
        summary_service: SummaryApplicationService,
        knowledge_service: KnowledgeApplicationService,
        model_service: ModelService,
    ) -> None:
        self._uow_factory = uow_factory
        self._transcription_service = transcription_service
        self._summary_service = summary_service
        self._knowledge_service = knowledge_service
        self._model_service = model_service

    async def run(self, meeting_id: str) -> None:
        stage = "preflight"
        try:
            logger.info(f"[{meeting_id}] 流水线启动")
            self._model_service.ensure_processing_models_ready()
            meeting = await self._get_meeting(meeting_id)

            if meeting.status in (
                MeetingStatus.UPLOADED,
                MeetingStatus.TRANSCRIBING,
                MeetingStatus.DIARIZING,
            ):
                if meeting.status in (MeetingStatus.UPLOADED, MeetingStatus.TRANSCRIBING):
                    stage = "asr"
                    await self._transcription_service.run_asr_if_needed(meeting_id)

                meeting = await self._get_meeting(meeting_id)
                if meeting.status == MeetingStatus.DIARIZING:
                    stage = "diarization"
                    await self._transcription_service.run_diarization_if_needed(meeting_id)

            meeting = await self._get_meeting(meeting_id)
            if meeting.status == MeetingStatus.SUMMARIZING:
                stage = "summarization"
                await self._summary_service.summarize_meeting(meeting_id)

            meeting = await self._get_meeting(meeting_id)
            if meeting.status == MeetingStatus.COMPLETED:
                stage = "knowledge_indexing"
                await self._knowledge_service.index_meeting(meeting_id)

            logger.info(f"[{meeting_id}] 流水线全部完成")
        except ModelNotReadyError as exc:
            logger.warning(f"[{meeting_id}] 模型未就绪: {exc}")
            await self._mark_failed(meeting_id, stage, str(exc))
        except Exception as exc:  # noqa: BLE001 - 流水线顶层需要兜底捕获，避免后台任务静默失败
            logger.exception(f"[{meeting_id}] 流水线在阶段 [{stage}] 失败: {exc}")
            await self._mark_failed(meeting_id, stage, _friendly_error(stage, str(exc)))

    async def _get_meeting(self, meeting_id: str):
        async with self._uow_factory() as uow:
            return await uow.meetings.get(MeetingId(meeting_id))

    async def _mark_failed(self, meeting_id: str, stage: str, reason: str) -> None:
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                return
            meeting.fail(stage=stage, reason=reason)
            await uow.meetings.save(meeting)
            await uow.commit()


def _friendly_error(stage: str, reason: str) -> str:
    """将底层异常转为用户可理解的错误说明。"""
    lower = reason.lower()
    if "ffmpeg" in lower:
        return "缺少 ffmpeg，无法解码 m4a/mp3 等音频。请运行 brew install ffmpeg 后点击「重试处理」。"
    if "hf_token" in lower or "gated" in lower or "401" in reason or "use_auth_token" in lower:
        return "pyannote 模型需要 HuggingFace Token。请在 .env 设置 MEMOFLOW_HF_TOKEN 并接受模型协议后重试。"
    if "mlx" in lower or "metal" in lower:
        return "摘要模型需要 Apple Silicon Mac 上的 MLX 环境。请确认在 M 系列 Mac 上运行。"
    if "不能执行操作" in reason and "transcribing" in lower:
        return "处理状态异常，请点击「重试处理」从上次成功的阶段继续。"
    stage_labels = {
        "preflight": "模型检查",
        "asr": "语音识别",
        "diarization": "说话人识别",
        "summarization": "摘要生成",
        "knowledge_indexing": "知识库索引",
    }
    label = stage_labels.get(stage, stage)
    return f"{label}阶段失败: {reason}"
