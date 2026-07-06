from dataclasses import dataclass

from genai_platform.adapters.cache.redis_cache import SemanticCache
from genai_platform.adapters.llm.mock_provider import MockLLMProvider
from genai_platform.adapters.metrics.prometheus_metrics import PrometheusMetrics
from genai_platform.adapters.tracing.langfuse_tracing import MetricsCollector
from genai_platform.adapters.vector_store.qdrant_store import QdrantVectorStore
from genai_platform.application.llm_gateway import LLMGateway
from genai_platform.application.query_service import QueryService
from genai_platform.application.rag_pipeline import RAGPipeline
from genai_platform.config import Settings
from genai_platform.domain.rate_limiting import RateLimiter
from genai_platform.ports.llm_provider import LLMProviderPort


@dataclass
class AppComponents:
    settings: Settings
    query_service: QueryService
    rate_limiter: RateLimiter
    rag: RAGPipeline


async def build_app_components(settings: Settings) -> AppComponents:
    try:
        import litellm  # noqa: F401

        from genai_platform.adapters.llm.litellm_provider import LiteLLMProvider

        llm_provider: LLMProviderPort = LiteLLMProvider()
    except ImportError:
        llm_provider = MockLLMProvider()

    gateway = LLMGateway(settings, llm_provider)

    vector_store = QdrantVectorStore(url=settings.qdrant_url)
    rag = RAGPipeline(settings, gateway, llm_provider, vector_store)
    await rag.initialize()

    cache = SemanticCache(redis_url=settings.redis_url, ttl=settings.cache_ttl)
    tracing = MetricsCollector(settings)
    metrics = PrometheusMetrics()
    metrics.init()

    query_service = QueryService(
        settings, rag, gateway, cache=cache, tracing=tracing, metrics=metrics
    )
    rate_limiter = RateLimiter(rpm=settings.rate_limit_rpm, tpm=settings.rate_limit_tpm)

    return AppComponents(
        settings=settings,
        query_service=query_service,
        rate_limiter=rate_limiter,
        rag=rag,
    )
