"""RerankPort 的 Qwen3-Rerank 实现。

调用 DashScope OpenAI 兼容 Rerank API（默认 `/reranks`），
也支持 SiliconFlow 等使用 `/rerank` 路径的兼容服务。
"""
from __future__ import annotations

from loguru import logger

from memoflow.application.ports.rerank_port import RerankPort

_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-api/v1"
_DEFAULT_MODEL = "qwen3-rerank"


class QwenReranker(RerankPort):
    def __init__(
        self,
        api_key: str = "",
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
        endpoint_path: str | None = None,
        endpoint_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._endpoint_path = endpoint_path
        self._endpoint_url = endpoint_url.strip() if endpoint_url else None
        self._timeout = timeout
        logger.debug(
            f"QwenReranker initialized: model={model}, endpoint={self._request_url()}"
        )

    def _resolve_endpoint_path(self) -> str:
        if self._endpoint_path:
            return self._endpoint_path if self._endpoint_path.startswith("/") else f"/{self._endpoint_path}"
        if "siliconflow" in self._base_url.lower():
            return "/rerank"
        return "/reranks"

    def _request_url(self) -> str:
        if self._endpoint_url:
            return self._endpoint_url
        return f"{self._base_url}{self._resolve_endpoint_path()}"

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents or top_n <= 0:
            return []
        if not self._api_key:
            raise RuntimeError(
                "未配置 Rerank API Key。请在 .env 中设置 MEMOFLOW_RERANK_API_KEY。"
            )

        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx package is required for QwenReranker; install with: pip install httpx"
            ) from exc

        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._request_url(), json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return self._parse_results(data, top_n)

    @staticmethod
    def _parse_results(data: dict, top_n: int) -> list[tuple[int, float]]:
        results = data.get("results")
        if results is None and isinstance(data.get("output"), dict):
            results = data["output"].get("results")
        if not isinstance(results, list):
            raise ValueError(f"Unexpected rerank response format: {data!r}")

        ranked: list[tuple[int, float]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if index is None or score is None:
                continue
            ranked.append((int(index), float(score)))

        ranked.sort(key=lambda pair: pair[1], reverse=True)
        return ranked[:top_n]
