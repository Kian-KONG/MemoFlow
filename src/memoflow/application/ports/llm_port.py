"""大语言模型（LLM）端口。

生产实现：`memoflow.infrastructure.ai.qwen_mlx_llm.QwenMLXLLM`
（基于 mlx-lm 在 Apple Silicon 上本地运行 Qwen3-14B）。
可替换为 llama.cpp / vLLM / 远程 OpenAI 兼容 API 等实现。
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
