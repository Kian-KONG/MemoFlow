"""组合根（Composition Root）：集中完成依赖注入装配。

这是全项目唯一"知道所有具体实现类"的地方 —— 领域层、应用层只依赖抽象端口（Port），
接口层（API/UI）只依赖应用服务。替换任意基础设施实现（如把 LanceDB 换成 Qdrant，
把 DeepSeek 换成其他 LLM）只需修改本文件中的一行装配代码。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from memoflow.application.knowledge_service import KnowledgeApplicationService
from memoflow.application.meeting_service import MeetingApplicationService
from memoflow.application.pipeline.processing_pipeline import MeetingProcessingPipeline
from memoflow.application.pipeline.runner import AsyncioPipelineRunner
from memoflow.application.ports.asr_port import ASRPort
from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.application.ports.file_storage_port import FileStoragePort
from memoflow.application.ports.llm_port import LLMPort
from memoflow.application.ports.pipeline_runner import PipelineRunner
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.application.summary_service import SummaryApplicationService
from memoflow.application.system_service import ModelService
from memoflow.application.transcription_service import TranscriptionApplicationService
from memoflow.config import Settings
from memoflow.domain.knowledge.repository import VectorRepository
from memoflow.domain.shared.events import EventDispatcher
from memoflow.infrastructure.ai.deepseek_llm import DeepSeekLLM
from memoflow.infrastructure.ai.openai_embedding import OpenAIEmbedding
from memoflow.infrastructure.ai.qwen_reranker import QwenReranker
from memoflow.infrastructure.ai.vibevoice_asr import VibeVoiceASR
from memoflow.infrastructure.persistence.db import create_engine, create_session_factory
from memoflow.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from memoflow.infrastructure.storage.file_storage import LocalFileStorage
from memoflow.infrastructure.vectorstore.lancedb_repository import LanceDBVectorRepository


@dataclass
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    uow_factory: UnitOfWorkFactory
    event_dispatcher: EventDispatcher

    file_storage: FileStoragePort
    asr: ASRPort
    llm: LLMPort
    embedding: EmbeddingPort
    reranker: QwenReranker
    vector_repository: VectorRepository

    meeting_service: MeetingApplicationService
    transcription_service: TranscriptionApplicationService
    summary_service: SummaryApplicationService
    knowledge_service: KnowledgeApplicationService
    system_service: ModelService

    pipeline: MeetingProcessingPipeline
    pipeline_runner: PipelineRunner


def build_container(settings: Settings) -> AppContainer:
    settings.ensure_directories()

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    event_dispatcher = EventDispatcher()

    # ---- 基础设施适配器（均可替换）----
    file_storage: FileStoragePort = LocalFileStorage(settings.audio_dir)
    asr: ASRPort = VibeVoiceASR(model_path=settings.asr_model_path, device=settings.asr_device)
    llm: LLMPort = DeepSeekLLM(
        api_key=settings.resolved_llm_api_key,
        base_url=settings.resolved_llm_base_url,
        model=settings.resolved_llm_model,
        default_max_tokens=settings.llm_max_tokens,
        default_temperature=settings.llm_temperature,
    )
    embedding: EmbeddingPort = OpenAIEmbedding(
        api_key=settings.resolved_embedding_api_key,
        base_url=settings.resolved_embedding_base_url,
        model=settings.resolved_embedding_model,
        dimensions=settings.embedding_dimensions,
    )
    reranker = QwenReranker(
        api_key=settings.resolved_rerank_api_key,
        base_url=settings.rerank_base_url,
        model=settings.resolved_rerank_model,
        endpoint_url=settings.reranker_api_url.strip() or None,
    )
    vector_repository: VectorRepository = LanceDBVectorRepository(str(settings.lancedb_dir))

    # ---- 应用服务 ----
    transcription_service = TranscriptionApplicationService(uow_factory, file_storage, asr)
    summary_service = SummaryApplicationService(
        uow_factory, llm, llm_model_name=settings.resolved_llm_model
    )
    knowledge_service = KnowledgeApplicationService(
        uow_factory,
        embedding,
        vector_repository,
        reranker=reranker,
        rerank_top_n=settings.rerank_top_n,
    )
    system_service = ModelService(settings, asr)

    pipeline = MeetingProcessingPipeline(
        uow_factory, transcription_service, summary_service, knowledge_service, system_service
    )
    pipeline_runner: PipelineRunner = AsyncioPipelineRunner(pipeline)

    meeting_service = MeetingApplicationService(uow_factory, file_storage, event_dispatcher, pipeline_runner)

    return AppContainer(
        settings=settings,
        engine=engine,
        uow_factory=uow_factory,
        event_dispatcher=event_dispatcher,
        file_storage=file_storage,
        asr=asr,
        llm=llm,
        embedding=embedding,
        reranker=reranker,
        vector_repository=vector_repository,
        meeting_service=meeting_service,
        transcription_service=transcription_service,
        summary_service=summary_service,
        knowledge_service=knowledge_service,
        system_service=system_service,
        pipeline=pipeline,
        pipeline_runner=pipeline_runner,
    )
