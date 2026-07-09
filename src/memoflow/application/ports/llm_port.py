"""大语言模型（LLM）端口。

生产实现：`memoflow.infrastructure.ai.deepseek_llm.DeepSeekLLM`
（通过 OpenAI 兼容接口调用 DeepSeek V4 Pro 远程 API）。
亦可替换为 llama.cpp / vLLM / 其他 OpenAI 兼容云端 API 等实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """给定 prompt（及可选 system prompt），返回模型生成的文本。"""
