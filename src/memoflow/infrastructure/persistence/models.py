"""SQLAlchemy ORM 模型（数据库表结构定义）。

领域模型与 ORM 模型严格分离：领域层不依赖 SQLAlchemy，
ORM 与领域实体之间的相互转换在 `mappers.py` 中完成。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memoflow.infrastructure.persistence.db import Base


class MeetingModel(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, index=True)

    storage_path: Mapped[str] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(nullable=False)
    content_type: Mapped[str] = mapped_column(nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    transcript_id: Mapped[str | None] = mapped_column(nullable=True)
    summary_id: Mapped[str | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(nullable=True)
    resume_status: Mapped[str | None] = mapped_column(nullable=True)


class TranscriptModel(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    speakers: Mapped[list["SpeakerModel"]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan", lazy="selectin"
    )
    utterances: Mapped[list["UtteranceModel"]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan", lazy="selectin"
    )


class SpeakerModel(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(primary_key=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(nullable=False)
    display_name: Mapped[str | None] = mapped_column(nullable=True)

    transcript: Mapped[TranscriptModel] = relationship(back_populates="speakers")


class UtteranceModel(Base):
    __tablename__ = "utterances"
    __table_args__ = (Index("ix_utterances_transcript_start", "transcript_id", "start"),)

    id: Mapped[str] = mapped_column(primary_key=True)
    transcript_id: Mapped[str] = mapped_column(ForeignKey("transcripts.id"), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(ForeignKey("speakers.id"), nullable=True)
    start: Mapped[float] = mapped_column(nullable=False)
    end: Mapped[float] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)

    transcript: Mapped[TranscriptModel] = relationship(back_populates="utterances")


class SummaryModel(Base):
    __tablename__ = "summaries"

    id: Mapped[str] = mapped_column(primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    overview: Mapped[str] = mapped_column(nullable=False)
    key_points: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generated_by_model: Mapped[str] = mapped_column(nullable=False)
    generated_at: Mapped[datetime] = mapped_column(nullable=False)

    decisions: Mapped[list["DecisionModel"]] = relationship(
        back_populates="summary", cascade="all, delete-orphan", lazy="selectin"
    )
    action_items: Mapped[list["ActionItemModel"]] = relationship(
        back_populates="summary", cascade="all, delete-orphan", lazy="selectin"
    )


class DecisionModel(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(primary_key=True)
    summary_id: Mapped[str] = mapped_column(ForeignKey("summaries.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(nullable=False)
    related_utterance_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    summary: Mapped[SummaryModel] = relationship(back_populates="decisions")


class ActionItemModel(Base):
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(primary_key=True)
    summary_id: Mapped[str] = mapped_column(ForeignKey("summaries.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(nullable=False)
    owner: Mapped[str | None] = mapped_column(nullable=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="open")
    related_utterance_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    summary: Mapped[SummaryModel] = relationship(back_populates="action_items")
