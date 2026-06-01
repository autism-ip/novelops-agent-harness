"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """NovelOps backend settings — loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Security ---
    BACKEND_API_KEY: str = ""

    # --- Feishu Bitable ---
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""

    # --- LLM ---
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"

    # --- OpenCLI ---
    OPENCLI_ENABLED: bool = False

    # --- CORS ---
    CORS_ORIGINS: str = "*"


settings = Settings()
