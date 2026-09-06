from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Look for .env in root or backend dir
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT_DIR / ".env" if (ROOT_DIR / ".env").exists() else Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH if ENV_PATH.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # API Server
    ares_api_base_url: str = Field(default="http://localhost:8000", alias="ARES_API_BASE_URL")

    # Groq (Primary)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    groq_default_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_DEFAULT_MODEL")

    # Google Gemini (Secondary)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_base_url: str = Field(default="https://generativelanguage.googleapis.com/v1beta/openai", alias="GEMINI_BASE_URL")
    gemini_default_model: str = Field(default="gemini-3.7-flash", alias="GEMINI_DEFAULT_MODEL")

    # NVIDIA NIM (Tertiary)
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL")
    nvidia_default_model: str = Field(default="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", alias="NVIDIA_DEFAULT_MODEL")

    # Vector DB (Qdrant)
    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="ares_attacks", alias="QDRANT_COLLECTION")
    qdrant_vector_size: int = Field(default=768, alias="QDRANT_VECTOR_SIZE")
    gemini_embedding_model: str = Field(default="models/gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL")

    # Role Assignments
    attacker_provider: str = Field(default="groq", alias="ATTACKER_PROVIDER")
    victim_provider: str = Field(default="groq", alias="VICTIM_PROVIDER")
    judge_provider: str = Field(default="gemini", alias="JUDGE_PROVIDER")

    # Resilience & Fallback Settings
    fallback_order: List[str] = Field(default_factory=lambda: ["groq", "gemini", "nvidia"])
    max_retries: int = 3
    retry_min_wait_seconds: float = 0.5
    retry_max_wait_seconds: float = 4.0
    request_timeout_seconds: float = 30.0


settings = Settings()
