from functools import lru_cache
from typing import Optional

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseModel):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="AI Gateway")
    version: str = Field(default="0.1.0")
    environment: str = Field(default_factory=lambda: os.getenv("APP_ENV", "local"))

    azure_openai_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT")
    )
    azure_openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY")
    )
    azure_openai_deployment: Optional[str] = Field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )

    chatbot_api_base_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("CHATBOT_API_BASE_URL")
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
