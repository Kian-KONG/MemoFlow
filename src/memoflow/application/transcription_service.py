"""转写应用服务：编排 ASR + 转写组装。"""
from __future__ import annotations

import asyncio

from loguru import logger

from memoflow.application.dto import TranscriptDTO
from memoflow.application.ports.asr_port import ASRPort
from memoflow.application.ports.file_storage_port import FileStoragePort
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.domain.meeting.value_objects import MeetingId, MeetingStatus
from memoflow.domain.shared.exceptions import EntityNotFoundError
from memoflow.domain.transcript.entities import Transcript
from memoflow.domain.transcript.services import (
    RawSpeakerSegment,
    RawUtteranceSegment,
    TranscriptAssemblyService,
)
from memoflow.domain.transcript.value_objects import TranscriptId
from memoflow.infrastructure.audio.ffmpeg import prepare_audio_for_asr

_BACKEND_LABELS = {
    "mlx_moss": "MOSS MLX",
    "moss_hf": "MOSS HF",
    "vibevoice": "VibeVoice",
}


def _asr_backend_label(asr: ASRPort) -> str:
    key = getattr(asr, "_backend_key", None)
    if key:
        return _BACKEND_LABELS.get(key, str(key))
    return getattr(asr, "source", "ASR")


class TranscriptionApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        file_storage: FileStoragePort,
        asr: ASRPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_storage = file_storage
        self._asr = asr

    def set_asr(self, asr: ASRPort) -> None:
        self._asr = asr

    async def run_asr_if_needed(self, meeting_id: str) -> Transcript | None:
        """语音识别阶段：若已有转写缓存则跳过。"""
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            if meeting.transcript_id is not None:
                transcript = await uow.transcripts.get(TranscriptId(meeting.transcript_id))
                if transcript is not None:
                    logger.info(f"[{meeting_id}] 跳过语音识别，使用已有转写缓存")
                    changed = False
                    if meeting.status in (MeetingStatus.UPLOADED, MeetingStatus.TRANSCRIBING):
                        meeting.complete_transcription(meeting.transcript_id)
                        changed = True
                    if transcript.speakers and meeting.status == MeetingStatus.DIARIZING:
                        meeting.complete_diarization()
                        changed = True
                    if changed:
                        await uow.meetings.save(meeting)
                        await uow.commit()
                    return transcript

            audio_path = await self._file_storage.resolve_path(meeting.audio.storage_path)
            meeting.ensure_transcribing()
            await uow.meetings.save(meeting)
            await uow.commit()

        backend = _asr_backend_label(self._asr)
        logger.info(f"[{meeting_id}] 开始语音识别（{backend}）...")
        asr_input, cleanup = await asyncio.to_thread(prepare_audio_for_asr, audio_path)
        try:
            asr_result = await self._asr.transcribe(str(asr_input))
        finally:
            if cleanup is not None:
                cleanup()

        asr_segments = [
            RawUtteranceSegment(start=s.start, end=s.end, text=s.text, confidence=s.confidence)
            for s in asr_result.segments
        ]
        speaker_segments = [
            RawSpeakerSegment(start=s.start, end=s.end, speaker_label=s.speaker_label)
            for s in asr_result.segments
            if s.speaker_label
        ]
        transcript = TranscriptAssemblyService.assemble(
            meeting_id=meeting_id,
            language=asr_result.language,
            asr_segments=asr_segments,
            speaker_segments=speaker_segments,
        )
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            await uow.transcripts.add(transcript)
            meeting.complete_transcription(str(transcript.id))
            meeting.complete_diarization()
            await uow.meetings.save(meeting)
            await uow.commit()
        logger.info(f"[{meeting_id}] 语音识别完成，共 {len(transcript.utterances)} 条话语")
        return transcript

    async def run_diarization_if_needed(self, meeting_id: str) -> TranscriptDTO:
        """说话人识别阶段：ASR 已在转写中标注说话人，此处仅推进状态。"""
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            if meeting.transcript_id is None:
                raise EntityNotFoundError("Transcript", "(meeting has no transcript yet)")
            transcript = await uow.transcripts.get(TranscriptId(meeting.transcript_id))
            if transcript is None:
                raise EntityNotFoundError("Transcript", meeting.transcript_id)

            if meeting.status != MeetingStatus.DIARIZING:
                return TranscriptDTO.from_domain(transcript)

            if transcript.speakers:
                logger.info(f"[{meeting_id}] 跳过说话人识别，使用已有说话人缓存")
            else:
                backend = _asr_backend_label(self._asr)
                logger.info(f"[{meeting_id}] {backend} 已在转写阶段标注说话人，推进状态")

            meeting.complete_diarization()
            await uow.meetings.save(meeting)
            await uow.commit()

        return TranscriptDTO.from_domain(transcript)

    async def transcribe_meeting(self, meeting_id: str) -> TranscriptDTO:
        """兼容入口：依次执行 ASR 与说话人识别（各阶段内部支持缓存跳过）。"""
        await self.run_asr_if_needed(meeting_id)
        return await self.run_diarization_if_needed(meeting_id)

    async def get_transcript(self, meeting_id: str) -> TranscriptDTO:
        async with self._uow_factory() as uow:
            transcript = await uow.transcripts.get_by_meeting_id(meeting_id)
        if transcript is None:
            raise EntityNotFoundError("Transcript", f"(meeting_id={meeting_id})")
        return TranscriptDTO.from_domain(transcript)
