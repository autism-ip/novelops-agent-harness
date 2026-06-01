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
    )

    # --- Security ---
    backend_api_key: str  # required, no default; env: BACKEND_API_KEY

    # --- Feishu Bitable ---
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # --- LLM ---
    llm_api_key: str = ""
    llm_provider: str = "openai"

    # --- OpenCLI ---
    opencli_enabled: bool = False

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Derived (set by create_app) ---
    app_version: str = "0.1.0"

    @field_validator("backend_api_key")
    @classmethod
    def reject_blank_key(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("BACKEND_API_KEY must not be blank")
        return v
