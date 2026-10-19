from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    supabase_url: str
    supabase_key: str

    # Comma-separated origins, or "*" for all.
    cors_origins: str = "*"

@lru_cache
def get_settings() -> Settings:
    return Settings()