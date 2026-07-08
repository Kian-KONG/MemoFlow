"""EmbeddingPort 的实现，基于 sentence-transformers（如 BAAI/bge-small-zh-v1.5）。

用于将会议转写片段与检索查询编码为向量，写入 / 检索 LanceDB 知识库。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.embedding_port import EmbeddingPort


class SentenceTransformerEmbedding(EmbeddingPort):
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None
        self._dimension: int | None = None
        self._load_lock = threading.Lock()

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            logger.info(f"加载 Embedding 模型: {self._model_name} (device={self._device}) ...")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=self._device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Embedding 模型加载完成，维度={self._dimension}")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def preload(self) -> None:
        await asyncio.to_thread(self._ensure_model_loaded)

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
