"""文本重排序（Rerank）端口，用于知识库检索结果精排。

生产实现：`memoflow.infrastructure.ai.qwen_reranker.QwenReranker`
（基于 DashScope / SiliconFlow 等 OpenAI 兼容 Rerank API）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class RerankPort(ABC):
    @abstractmethod
    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        """Return list of (original_index, score) sorted by relevance desc, length <= top_n."""
