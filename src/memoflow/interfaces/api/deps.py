"""FastAPI 依赖注入 Provider：从 `app.state.container`（组合根）中取出应用服务。"""
from __future__ import annotations

from fastapi import Request

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.application.meeting_service import MeetingApplicationService
from memoflow.application.summary_service import SummaryApplicationService
from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_meeting_service(request: Request) -> MeetingApplicationService:
    return get_container(request).meeting_service


def get_transcription_service(request: Request) -> TranscriptionApplicationService:
    return get_container(request).transcription_service


def get_summary_service(request: Request) -> SummaryApplicationService:
    return get_container(request).summary_service


def get_knowledge_service(request: Request) -> KnowledgeApplicationService:
    return get_container(request).knowledge_service
