from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GENAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_version: str = "0.1.0"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    gateway_url: str = "http://gateway:4000"
    qdrant_url: str = "http://qdrant:6333"
    redis_url: str = "redis://redis:6379/0"
    langfuse_host: str = "http://langfuse:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    llm_default_model: str = "gpt-4o"
    llm_fallback_models: list[str] = ["claude-3-sonnet", "mistral-large"]
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    llm_request_timeout: int = 30

    rag_chunk_size: int = 512
    rag_chunk_overlap: float = 0.1
    rag_top_k: int = 20
    rag_rerank_top_k: int = 5
    rag_embedding_model: str = "text-embedding-3-large"
    rag_rerank_model: str = "cohere/rerank-v3.5"
    rag_collection_name: str = "documents"

    cache_ttl: int = 3600
    cache_similarity_threshold: float = 0.92

    rate_limit_rpm: int = 1000
    rate_limit_tpm: int = 100000

    api_keys: list[str] = []

    circuit_breaker_failures: int = 5
    circuit_breaker_timeout: int = 60

    guardrails_pii_entities: list[str] = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "SSN",
        "PERSON",
    ]
    guardrails_toxicity_threshold: float = 0.7
