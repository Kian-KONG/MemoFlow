"""FastAPI 请求 / 响应 Pydantic Schema（接口层，与领域模型解耦）。"""
from __future__ import annotations

from datetime import date, datetime

from typing import Literal

from pydantic import BaseModel, Field


class MeetingResponse(BaseModel):
    id: str
    title: str
    status: str
    original_filename: str
    duration_seconds: float | None
    created_at: datetime
    updated_at: datetime
    transcript_id: str | None
    summary_id: str | None
    error_message: str | None


class SpeakerResponse(BaseModel):
    id: str
    label: str
    display_name: str | None


class UtteranceResponse(BaseModel):
    id: str
    start: float
    end: float
    text: str
    speaker: SpeakerResponse | None
    confidence: float | None


class TranscriptResponse(BaseModel):
    id: str
    meeting_id: str
    language: str
    utterances: list[UtteranceResponse]
    speakers: list[SpeakerResponse]


class DecisionResponse(BaseModel):
    id: str
    description: str
    related_utterance_ids: list[str]


class ActionItemResponse(BaseModel):
    id: str
    description: str
    owner: str | None
    due_date: date | None
    status: str
    related_utterance_ids: list[str]


class SummaryResponse(BaseModel):
    id: str
    meeting_id: str
    overview: str
    key_points: list[str]
    decisions: list[DecisionResponse]
    action_items: list[ActionItemResponse]
    generated_by_model: str
    generated_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    meeting_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class KnowledgeHitResponse(BaseModel):
    chunk_id: str
    meeting_id: str
    text: str
    score: float
    source_utterance_ids: list[str]


class ErrorResponse(BaseModel):
    detail: str


class DependencyStatusResponse(BaseModel):
    name: str
    available: bool
    hint: str


class AsrOptionStatusResponse(BaseModel):
    backend: str
    label: str
    model_id: str
    model_path: str
    ready: bool
    source: str
    configured: bool
    active: bool
    download_command: str
    hint: str


class ModelStatusResponse(BaseModel):
    key: str
    role: str
    model_id: str
    loaded: bool
    ready: bool
    downloading: bool
    source: str
    progress_percent: float
    progress_message: str
    recent_logs: list[str]
    status: str
    hint: str


class ModelDownloadResponse(BaseModel):
    key: str
    message: str


class SystemStatusResponse(BaseModel):
    platform: str
    all_ready: bool
    configured_asr_backend: str = ""
    active_asr_backend: str = ""
    dependencies: list[DependencyStatusResponse]
    models: list[ModelStatusResponse]
    asr_options: list[AsrOptionStatusResponse] = []


class SelectAsrBackendRequest(BaseModel):
    backend: Literal["mlx_moss", "moss_hf", "vibevoice"]


class SelectAsrBackendResponse(BaseModel):
    backend: str
    active_asr_backend: str
    message: str
    status: SystemStatusResponse
