"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """NovelOps backend settings — loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Security ---
    BACKEND_API_KEY: str  # required, no default

    # --- Feishu Bitable ---
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""

    # --- LLM ---
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"

    # --- OpenCLI ---
    OPENCLI_ENABLED: bool = False
    opencli_bin: str = "opencli"
    opencli_timeout: int = 30

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Derived (set by create_app) ---
    APP_VERSION: str = "0.1.0"

    @field_validator("BACKEND_API_KEY")
    @classmethod
    def reject_blank_key(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BACKEND_API_KEY must not be blank")
        return v
