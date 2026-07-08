"""转写结果查询 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.interfaces.api.deps import get_transcription_service
from memoflow.interfaces.api.schemas import SpeakerResponse, TranscriptResponse, UtteranceResponse

router = APIRouter(prefix="/api/meetings", tags=["transcripts"])


@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse, summary="获取会议转写结果")
async def get_transcript(
    meeting_id: str, service: TranscriptionApplicationService = Depends(get_transcription_service)
) -> TranscriptResponse:
    dto = await service.get_transcript(meeting_id)
    return TranscriptResponse(
        id=dto.id,
        meeting_id=dto.meeting_id,
        language=dto.language,
        speakers=[
            SpeakerResponse(id=s.id, label=s.label, display_name=s.display_name) for s in dto.speakers
        ],
        utterances=[
            UtteranceResponse(
                id=u.id,
                start=u.start,
                end=u.end,
                text=u.text,
                confidence=u.confidence,
                speaker=(
                    SpeakerResponse(id=u.speaker.id, label=u.speaker.label, display_name=u.speaker.display_name)
                    if u.speaker
                    else None
                ),
            )
            for u in dto.utterances
        ],
    )
