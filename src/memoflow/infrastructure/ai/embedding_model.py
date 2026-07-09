"""EmbeddingPort 的实现，基于 sentence-transformers（如 BAAI/bge-small-zh-v1.5）。

用于将会议转写片段与检索查询编码为向量，写入 / 检索 LanceDB 知识库。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.embedding_port import EmbeddingPort
from memoflow.infrastructure.ai.modelscope_download import snapshot_download_with_progress
from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_SOURCE = "ModelScope"


class SentenceTransformerEmbedding(EmbeddingPort):
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._dimension: int | None = None
        self._load_lock = threading.Lock()
        self._local_model_path: str | None = None

    @property
    def source(self) -> str:
        return _SOURCE

    def _ensure_model_loaded(self, on_progress: ProgressCallback = None) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            report_progress(on_progress, 5, f"连接 ModelScope · {self._model_name}")
            self._local_model_path = snapshot_download_with_progress(
                self._model_name,
                on_progress,
                progress_range=(10, 85),
                label=self._model_name,
            )
            report_progress(on_progress, 90, "下载完成，开始加载 Embedding...")
            logger.info(f"加载 Embedding 模型: {self._model_name} (device={self._device}) ...")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._local_model_path or self._model_name, device=self._device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            report_progress(on_progress, 100, f"Embedding 已就绪，维度={self._dimension}")
            logger.info(f"Embedding 模型加载完成，维度={self._dimension}")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def preload(self, on_progress: ProgressCallback = None) -> None:
        await asyncio.to_thread(self._ensure_model_loaded, on_progress)

    def _require_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError("Embedding 模型尚未下载，请前往设置页下载后再处理会议。")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        self._require_loaded()
        assert self._model is not None
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        self._ensure_model_loaded()
        assert self._dimension is not None
        return self._dimension
