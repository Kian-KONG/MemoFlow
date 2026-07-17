"""DeepSeekLLM 错误提示应覆盖 DeepSeek 与 Bosch 两种 Key。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError

from memoflow.infrastructure.ai.deepseek_llm import DeepSeekLLM


def test_missing_api_key_mentions_deepseek_and_bosch() -> None:
    llm = DeepSeekLLM(api_key="")
    with pytest.raises(RuntimeError) as exc_info:
        llm._get_client()
    message = str(exc_info.value)
    assert "MEMOFLOW_DEEPSEEK_API_KEY" in message
    assert "BOSCH_AIGC_API_KEY" in message


def test_auth_error_mentions_deepseek_and_bosch() -> None:
    wrapped = DeepSeekLLM._wrap_api_error(MagicMock(spec=AuthenticationError))
    message = str(wrapped)
    assert "MEMOFLOW_DEEPSEEK_API_KEY" in message
    assert "BOSCH_AIGC_API_KEY" in message
