"""知识库语义检索 API（RAG 检索入口）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.interfaces.api.deps import get_knowledge_service
from memoflow.interfaces.api.schemas import KnowledgeHitResponse, KnowledgeSearchRequest

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/search", response_model=list[KnowledgeHitResponse], summary="知识库语义检索")
async def search_knowledge(
    request: KnowledgeSearchRequest,
    service: KnowledgeApplicationService = Depends(get_knowledge_service),
) -> list[KnowledgeHitResponse]:
    hits = await service.search(query=request.query, meeting_id=request.meeting_id, top_k=request.top_k)
    return [
        KnowledgeHitResponse(
            chunk_id=h.chunk_id,
            meeting_id=h.meeting_id,
            text=h.text,
            score=h.score,
            source_utterance_ids=h.source_utterance_ids,
        )
        for h in hits
    ]
