"""摘要 / 决策 / 行动项 查询 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from memoflow.application.summary_service import SummaryApplicationService
from memoflow.interfaces.api.deps import get_summary_service
from memoflow.interfaces.api.schemas import ActionItemResponse, DecisionResponse, SummaryResponse

router = APIRouter(prefix="/api/meetings", tags=["summaries"])


@router.get("/{meeting_id}/summary", response_model=SummaryResponse, summary="获取会议摘要")
async def get_summary(
    meeting_id: str, service: SummaryApplicationService = Depends(get_summary_service)
) -> SummaryResponse:
    dto = await service.get_summary(meeting_id)
    return SummaryResponse(
        id=dto.id,
        meeting_id=dto.meeting_id,
        overview=dto.overview,
        key_points=dto.key_points,
        generated_by_model=dto.generated_by_model,
        generated_at=dto.generated_at,
        decisions=[
            DecisionResponse(id=d.id, description=d.description, related_utterance_ids=d.related_utterance_ids)
            for d in dto.decisions
        ],
        action_items=[
            ActionItemResponse(
                id=a.id,
                description=a.description,
                owner=a.owner,
                due_date=a.due_date,
                status=a.status.value,
                related_utterance_ids=a.related_utterance_ids,
            )
            for a in dto.action_items
        ],
    )
