"""处理管线友好错误信息应反映实际 Key 解析路径。"""
from __future__ import annotations

from memoflow.application.pipeline.processing_pipeline import _friendly_error


def test_summarization_api_key_error_mentions_bosch() -> None:
    message = _friendly_error("summarization", "DeepSeek API 认证失败，请检查 API Key")
    assert "MEMOFLOW_DEEPSEEK_API_KEY" in message
    assert "BOSCH_AIGC_API_KEY" in message
