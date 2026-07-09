"""EmbeddingPort 的 OpenAI 实现（text-embedding-3 系列）。

通过 OpenAI Embeddings API 将会议转写片段与检索查询编码为向量，
写入 / 检索 LanceDB 知识库。
"""
from __future__ import annotations

from loguru import logger

from memoflow.application.ports.embedding_port import EmbeddingPort

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "text-embedding-3-small"

_MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-v3": 1024,
}


class OpenAIEmbedding(EmbeddingPort):
    def __init__(
        self,
        api_key: str = "",
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
        dimensions: int | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model
        self._dimensions = dimensions
        self._base_url = base_url.rstrip("/")
        self._client = None
        logger.debug(f"OpenAIEmbedding initialized: model={model}, base_url={self._base_url}")

    def _get_client(self):
        if not self._api_key:
            raise RuntimeError(
                "未配置 OpenAI API Key。请在 .env 中设置 MEMOFLOW_OPENAI_API_KEY。"
            )
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise ImportError(
                    "openai package is required for OpenAIEmbedding; install with: pip install openai"
                ) from exc
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        kwargs: dict = {"model": self._model, "input": texts}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        response = await client.embeddings.create(**kwargs)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    @property
    def dimension(self) -> int:
        if self._dimensions is not None:
            return self._dimensions
        if self._model in _MODEL_DIMENSIONS:
            return _MODEL_DIMENSIONS[self._model]
        raise ValueError(
            f"Unknown embedding model dimension for {self._model!r}; set dimensions explicitly"
        )
