"""聚合所有 API 子路由。"""
from __future__ import annotations

from fastapi import APIRouter

from memoflow.interfaces.api.routes import knowledge, meetings, summaries, transcripts

api_router = APIRouter()
api_router.include_router(meetings.router)
api_router.include_router(transcripts.router)
api_router.include_router(summaries.router)
api_router.include_router(knowledge.router)
