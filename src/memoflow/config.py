"""应用配置（基于 pydantic-settings，从环境变量 / .env 加载）。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMOFLOW_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "MemoFlow"
    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    secret_key: str = "change-me-in-production"

    data_dir: Path = Path("./data")
    database_url: str = "sqlite+aiosqlite:///./data/memoflow.db"
    lancedb_dir: Path = Path("./data/lancedb")
    audio_dir: Path = Path("./data/audio")

    # VibeVoice ASR（本地权重，通过 scripts/download_vibevoice_asr.sh 下载）
    asr_model_path: Path = Path("./models/VibeVoice-ASR")
    asr_device: str = "auto"  # auto|cpu|mps|cuda

    # DeepSeek LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # OpenAI Embedding
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int | None = None

    # Qwen3 Reranker（DashScope 兼容 API）
    rerank_api_key: str = ""
    rerank_base_url: str = "https://dashscope.aliyuncs.com/compatible-api/v1"
    rerank_model: str = "qwen3-rerank"
    rerank_top_n: int = 5

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.lancedb_dir, self.audio_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
