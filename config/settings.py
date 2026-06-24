from __future__ import annotations

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Pipeline
    chunk_size: int = 10
    max_retries: int = 3
    hitl_confidence_threshold: float = 0.7

    # Embedding
    embedding_model: str = "BAAI/bge-large-zh-v1.5"

    # Output paths
    vectordb_path: str = "./outputs/vectordb/"
    output_dir: str = "./outputs/"

    # Taxonomy file
    taxonomy_path: str = "config/taxonomy.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the project root."""
        return Path(relative_path)


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the global Settings singleton, loading .env if available."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
