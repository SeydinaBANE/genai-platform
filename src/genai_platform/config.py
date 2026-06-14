from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENAI_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_version: str = "0.1.0"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    gateway_url: str = "http://gateway:4000"
    qdrant_url: str = "http://qdrant:6333"
    redis_url: str = "redis://redis:6379/0"
    langfuse_host: str = "http://langfuse:3000"
