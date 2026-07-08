"""LLMPort 的 Qwen3-14B (MLX) 实现，专为 Apple Silicon 本地推理设计。

使用 `mlx-lm` 在本机 GPU（Metal）上运行量化后的 Qwen3-14B 模型，
全程无需联网，符合"本地部署"要求。
"""
from __future__ import annotations

import asyncio
import threading

from loguru import logger

from memoflow.application.ports.llm_port import LLMPort


class QwenMLXLLM(LLMPort):
    def __init__(
        self,
        model_path: str = "mlx-community/Qwen3-14B-4bit",
        default_max_tokens: int = 2048,
        default_temperature: float = 0.3,
    ) -> None:
        self._model_path = model_path
        self._default_max_tokens = default_max_tokens
        self._default_temperature = default_temperature
        self._model = None
        self._tokenizer = None
        self._load_lock = threading.Lock()

    def _ensure_model_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            logger.info(f"加载 Qwen3 (MLX) 模型: {self._model_path} ...")
            from mlx_lm import load

            self._model, self._tokenizer = load(self._model_path)
            logger.info("Qwen3 (MLX) 模型加载完成")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def preload(self) -> None:
        await asyncio.to_thread(self._ensure_model_loaded)

    def _require_loaded(self) -> None:
        if self._model is None:
            raise RuntimeError("Qwen3 模型尚未下载，请前往设置页下载后再处理会议。")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        return await asyncio.to_thread(self._generate_sync, prompt, system_prompt, max_tokens, temperature)

    def _generate_sync(
        self,
        prompt: str,
        system_prompt: str | None,
        max_tokens: int | None,
        temperature: float | None,
    ) -> str:
        self._require_loaded()
        assert self._model is not None and self._tokenizer is not None
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        formatted_prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        sampler = make_sampler(temp=temperature if temperature is not None else self._default_temperature)
        response = generate(
            self._model,
            self._tokenizer,
            prompt=formatted_prompt,
            max_tokens=max_tokens or self._default_max_tokens,
            sampler=sampler,
            verbose=False,
        )
        return response.strip()
