"""转写应用服务：编排 ASR + 说话人识别 + 转写组装。"""
from __future__ import annotations

from loguru import logger

from memoflow.application.dto import TranscriptDTO
from memoflow.application.ports.asr_port import ASRPort
from memoflow.application.ports.diarization_port import DiarizationPort
from memoflow.application.ports.file_storage_port import FileStoragePort
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.domain.meeting.value_objects import MeetingId
from memoflow.domain.shared.exceptions import EntityNotFoundError
from memoflow.domain.transcript.services import (
    RawSpeakerSegment,
    RawUtteranceSegment,
    TranscriptAssemblyService,
)


class TranscriptionApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        file_storage: FileStoragePort,
        asr: ASRPort,
        diarization: DiarizationPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_storage = file_storage
        self._asr = asr
        self._diarization = diarization

    async def transcribe_meeting(self, meeting_id: str) -> TranscriptDTO:
        """对指定会议执行 ASR + 说话人识别，分阶段持久化转写与会议状态。

        分阶段的意义：ASR 与说话人识别都可能耗时较长（尤其是首次需要下载/加载模型），
        每个阶段完成后立即提交会议状态与已产出的转写数据，
        这样前端轮询时能实时看到"转写中 -> 说话人识别中 -> 已生成转写文本"的真实进度，
        而不是等到整个流水线结束才有任何可见变化。
        """
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            audio_path = await self._file_storage.resolve_path(meeting.audio.storage_path)
            meeting.start_transcribing()
            await uow.meetings.save(meeting)
            await uow.commit()

        logger.info(f"[{meeting_id}] 开始语音识别（SenseVoice）...")
        asr_result = await self._asr.transcribe(audio_path)

        # ASR 完成后先不带说话人信息组装转写并保存，让用户尽快看到转写文本内容
        transcript = TranscriptAssemblyService.assemble(
            meeting_id=meeting_id,
            language=asr_result.language,
            asr_segments=[
                RawUtteranceSegment(start=s.start, end=s.end, text=s.text, confidence=s.confidence)
                for s in asr_result.segments
            ],
            speaker_segments=[],
        )
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            await uow.transcripts.add(transcript)
            meeting.complete_transcription(str(transcript.id))
            await uow.meetings.save(meeting)
            await uow.commit()
        logger.info(f"[{meeting_id}] 语音识别完成，共 {len(transcript.utterances)} 条话语，开始说话人识别...")

        speaker_segments = await self._diarization.diarize(audio_path)

        # 说话人识别完成后回填已保存的转写，再整体更新
        TranscriptAssemblyService.assign_speakers(
            transcript,
            [
                RawSpeakerSegment(start=s.start, end=s.end, speaker_label=s.speaker_label)
                for s in speaker_segments
            ],
        )
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            await uow.transcripts.save(transcript)
            meeting.complete_diarization()
            await uow.meetings.save(meeting)
            await uow.commit()

        logger.info(f"[{meeting_id}] 说话人识别完成")
        return TranscriptDTO.from_domain(transcript)

    async def get_transcript(self, meeting_id: str) -> TranscriptDTO:
        async with self._uow_factory() as uow:
            transcript = await uow.transcripts.get_by_meeting_id(meeting_id)
        if transcript is None:
            raise EntityNotFoundError("Transcript", f"(meeting_id={meeting_id})")
        return TranscriptDTO.from_domain(transcript)
