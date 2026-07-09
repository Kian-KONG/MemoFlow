"""LLMPort 的 DeepSeek V4 Pro 远程 API 实现。

通过 OpenAI 兼容接口调用 DeepSeek API，无需本地下载或预加载模型。
"""
from __future__ import annotations

from loguru import logger

from memoflow.application.ports.llm_port import LLMPort

_SOURCE = "DeepSeek API"
_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-v4-pro"


class DeepSeekLLM(LLMPort):
    def __init__(
        self,
        api_key: str = "",
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
        default_max_tokens: int = 2048,
        default_temperature: float = 0.3,
    ) -> None:
        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._default_temperature = default_temperature
        self._client = None

    @property
    def source(self) -> str:
        return _SOURCE

    @property
    def is_loaded(self) -> bool:
        """远程 API：已配置有效 API Key 即视为可用。"""
        return bool(self._api_key)

    def _get_client(self):
        if not self._api_key:
            raise RuntimeError(
                "未配置 DeepSeek API Key。请在 .env 中设置 MEMOFLOW_DEEPSEEK_API_KEY。"
            )
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    @staticmethod
    def _is_json_task(system_prompt: str | None, prompt: str) -> bool:
        combined = f"{system_prompt or ''}\n{prompt}".lower()
        return "json" in combined

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        client = self._get_client()

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens or self._default_max_tokens,
            "temperature": temperature if temperature is not None else self._default_temperature,
        }
        if self._is_json_task(system_prompt, prompt):
            request_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            response = await client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            raise self._wrap_api_error(exc) from exc

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("DeepSeek API 返回空内容")
        return content.strip()

    @staticmethod
    def _wrap_api_error(exc: Exception) -> RuntimeError:
        from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

        if isinstance(exc, AuthenticationError):
            logger.error("DeepSeek API 认证失败，请检查 API Key")
            return RuntimeError("DeepSeek API 认证失败，请检查 MEMOFLOW_DEEPSEEK_API_KEY 是否正确。")
        if isinstance(exc, RateLimitError):
            logger.error(f"DeepSeek API 请求频率超限: {exc}")
            return RuntimeError("DeepSeek API 请求频率超限，请稍后重试。")
        if isinstance(exc, APIConnectionError):
            logger.error(f"DeepSeek API 连接失败: {exc}")
            return RuntimeError(f"无法连接 DeepSeek API，请检查网络与 base_url 配置。详情: {exc}")
        if isinstance(exc, APIStatusError):
            logger.error(f"DeepSeek API HTTP 错误 {exc.status_code}: {exc.message}")
            return RuntimeError(f"DeepSeek API 请求失败 (HTTP {exc.status_code}): {exc.message}")
        logger.error(f"DeepSeek API 调用异常: {exc}")
        return RuntimeError(f"DeepSeek API 调用失败: {exc}")
