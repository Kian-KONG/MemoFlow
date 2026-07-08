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

    # ASR: SenseVoice (FunASR)
    asr_model: str = "iic/SenseVoiceSmall"
    asr_device: str = "cpu"

    # Diarization: pyannote
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: str = ""

    # LLM: Qwen3-14B (MLX)
    llm_model_path: str = "mlx-community/Qwen3-14B-4bit"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.lancedb_dir, self.audio_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
