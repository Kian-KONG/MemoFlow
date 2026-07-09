"""应用配置（基于 pydantic-settings，从环境变量 / .env 加载）。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from memoflow.infrastructure.ai.asr_defaults import (
    default_asr_backend,
    default_asr_model_id,
    default_asr_model_path,
)


def _strip_api_suffix(url: str, suffix: str) -> str:
    value = url.rstrip("/")
    if value.endswith(suffix):
        return value[: -len(suffix)].rstrip("/")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMOFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
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

    # ASR（本地权重，通过 scripts/download_asr_model.sh 下载）
    # Mac Apple Silicon 默认 mlx_moss（~1.8GB）；其他平台默认 vibevoice
    asr_backend: str = Field(default_factory=default_asr_backend)  # mlx_moss | moss_hf | vibevoice | auto
    asr_model_id: str = Field(default="")
    asr_model_path: Path = Field(default=Path("."))
    asr_device: str = "auto"  # auto|cpu|mps|cuda
    asr_max_tokens: int = 4096

    @field_validator("asr_model_id", mode="before")
    @classmethod
    def _fill_asr_model_id(cls, value: object, info) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        backend = info.data.get("asr_backend") if info.data else None
        if backend == "auto" or not backend:
            backend = default_asr_backend()
        return default_asr_model_id(str(backend))

    @field_validator("asr_model_path", mode="before")
    @classmethod
    def _fill_asr_model_path(cls, value: object, info) -> Path:
        if value not in (None, "", "."):
            return Path(value).expanduser()
        backend = info.data.get("asr_backend") if info.data else None
        if backend == "auto" or not backend:
            backend = default_asr_backend()
        model_id = info.data.get("asr_model_id") if info.data else None
        if isinstance(model_id, str) and model_id.strip():
            return Path(default_asr_model_path(str(backend), model_id.strip()))
        return Path(default_asr_model_path(str(backend)))

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

    # Bosch AIGC 网关（无 MEMOFLOW_ 前缀，与现有 Bosch 部署变量兼容）
    bosch_aigc_api_key: str = Field(default="", validation_alias="BOSCH_AIGC_API_KEY")
    llm_api_url: str = Field(default="", validation_alias="LLM_API_URL")
    llm_model: str = Field(default="", validation_alias="LLM_MODEL")
    embedding_api_url: str = Field(default="", validation_alias="EMBEDDING_API_URL")
    embedding_model_alias: str = Field(default="", validation_alias="EMBEDDING_MODEL")
    reranker_api_url: str = Field(default="", validation_alias="RERANKER_API_URL")
    reranker_model_alias: str = Field(default="", validation_alias="RERANKER_MODEL")

    @property
    def resolved_api_key(self) -> str:
        return self.bosch_aigc_api_key or self.deepseek_api_key or self.openai_api_key or self.rerank_api_key

    @property
    def resolved_llm_api_key(self) -> str:
        return self.deepseek_api_key or self.bosch_aigc_api_key

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.openai_api_key or self.bosch_aigc_api_key

    @property
    def resolved_rerank_api_key(self) -> str:
        return self.rerank_api_key or self.bosch_aigc_api_key

    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_api_url.strip():
            return _strip_api_suffix(self.llm_api_url.strip(), "/chat/completions")
        return self.deepseek_base_url.rstrip("/")

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model.strip() or self.deepseek_model

    @property
    def resolved_embedding_base_url(self) -> str:
        if self.embedding_api_url.strip():
            return _strip_api_suffix(self.embedding_api_url.strip(), "/embeddings")
        return self.openai_base_url.rstrip("/")

    @property
    def resolved_embedding_model(self) -> str:
        return self.embedding_model_alias.strip() or self.embedding_model

    @property
    def resolved_rerank_endpoint_url(self) -> str:
        if self.reranker_api_url.strip():
            return self.reranker_api_url.strip()
        return f"{self.rerank_base_url.rstrip('/')}{self._default_rerank_path()}"

    @property
    def resolved_rerank_model(self) -> str:
        return self.reranker_model_alias.strip() or self.rerank_model

    @staticmethod
    def _default_rerank_path() -> str:
        return "/reranks"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.lancedb_dir, self.audio_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
