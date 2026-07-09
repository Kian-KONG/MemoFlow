"""文本向量化（Embedding）端口，用于知识库检索（RAG）。

生产实现：`memoflow.infrastructure.ai.openai_embedding.OpenAIEmbedding`
（OpenAI text-embedding-3 系列，远程 API）。
亦可替换为任意兼容 Embeddings API 或本地 sentence-transformers 实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表批量编码为向量列表。"""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度。"""
