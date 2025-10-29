"""Configuration management for Personal RAG system."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Embedding Configuration
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    embedding_dimensions: int = Field(default=1536, description="Embedding vector dimensions")

    # LLM Configuration
    llm_model: str = Field(default="gpt-5", description="OpenAI LLM model for generation")
    llm_temperature: float = Field(default=0.7, description="LLM temperature for generation")
    llm_streaming: bool = Field(default=True, description="Enable streaming responses")

    # Chunking Configuration
    chunk_size: int = Field(default=512, description="Target chunk size in tokens")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks in tokens")

    # Retrieval Configuration
    top_k: int = Field(default=5, description="Number of chunks to retrieve")
    similarity_threshold: Optional[float] = Field(
        default=None, description="Minimum similarity score for retrieval"
    )

    # ChromaDB Configuration
    chroma_persist_dir: str = Field(
        default="./data/chroma", description="ChromaDB persistence directory"
    )
    chroma_collection_name: str = Field(
        default="personal_docs", description="ChromaDB collection name"
    )

    # Google Drive Configuration
    google_client_id: Optional[str] = Field(default=None, description="Google OAuth client ID")
    google_client_secret: Optional[str] = Field(
        default=None, description="Google OAuth client secret"
    )
    google_credentials_file: str = Field(
        default="credentials.json", description="Google OAuth credentials file path"
    )
    google_token_file: str = Field(
        default="token.json", description="Google OAuth token file path"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")

    @property
    def chroma_persist_path(self) -> Path:
        """Get ChromaDB persistence directory as Path object."""
        path = Path(self.chroma_persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def google_credentials_path(self) -> Path:
        """Get Google credentials file path as Path object."""
        return Path(self.google_credentials_file)

    @property
    def google_token_path(self) -> Path:
        """Get Google token file path as Path object."""
        return Path(self.google_token_file)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings
