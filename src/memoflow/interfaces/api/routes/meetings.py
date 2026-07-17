"""会议相关 API：上传、查询、重试处理流水线。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from memoflow.application.meeting_service import MeetingApplicationService
from memoflow.config import get_settings
from memoflow.domain.meeting.value_objects import MeetingStatus
from memoflow.interfaces.api.deps import get_meeting_service
from memoflow.interfaces.api.schemas import MeetingResponse
from memoflow.interfaces.api.upload_stream import UploadTooLargeError, read_upload_limited

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _to_response(dto) -> MeetingResponse:  # noqa: ANN001
    return MeetingResponse(
        id=dto.id,
        title=dto.title,
        status=dto.status.value,
        original_filename=dto.original_filename,
        duration_seconds=dto.duration_seconds,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
        transcript_id=dto.transcript_id,
        summary_id=dto.summary_id,
        error_message=dto.error_message,
    )


@router.post("", response_model=MeetingResponse, status_code=201, summary="上传会议录音")
async def upload_meeting(
    file: UploadFile = File(..., description="会议录音文件（mp3/wav/m4a/flac 等）"),
    title: str = Form(default="", description="会议标题，留空则使用文件名"),
    service: MeetingApplicationService = Depends(get_meeting_service),
) -> MeetingResponse:
    max_bytes = get_settings().max_upload_bytes
    try:
        content = await read_upload_limited(file, max_bytes=max_bytes)
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc

    dto = await service.upload_meeting(
        title=title,
        filename=file.filename or "recording",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return _to_response(dto)


@router.get("", response_model=list[MeetingResponse], summary="会议列表")
async def list_meetings(
    status: MeetingStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: MeetingApplicationService = Depends(get_meeting_service),
) -> list[MeetingResponse]:
    dtos = await service.list_meetings(status=status, limit=limit, offset=offset)
    return [_to_response(dto) for dto in dtos]


@router.get("/{meeting_id}", response_model=MeetingResponse, summary="会议详情")
async def get_meeting(
    meeting_id: str, service: MeetingApplicationService = Depends(get_meeting_service)
) -> MeetingResponse:
    dto = await service.get_meeting(meeting_id)
    return _to_response(dto)


@router.post("/{meeting_id}/retry", response_model=MeetingResponse, summary="重试失败的处理流水线")
async def retry_meeting(
    meeting_id: str, service: MeetingApplicationService = Depends(get_meeting_service)
) -> MeetingResponse:
    dto = await service.retry_meeting(meeting_id)
    return _to_response(dto)
