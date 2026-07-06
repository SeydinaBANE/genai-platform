import json

from genai_platform.application.guardrails import InputGuardrails, OutputGuardrails
from genai_platform.application.llm_gateway import AllModelsFailedError, LLMGateway
from genai_platform.application.rag_pipeline import RAGPipeline
from genai_platform.config import Settings
from genai_platform.ports.cache import CachePort
from genai_platform.ports.metrics import MetricsPort
from genai_platform.ports.tracing import TracingPort


class QueryService:
    def __init__(
        self,
        settings: Settings,
        rag: RAGPipeline,
        gateway: LLMGateway,
        cache: CachePort,
        tracing: TracingPort,
        metrics: MetricsPort,
    ) -> None:
        self.settings = settings
        self.rag = rag
        self.gateway = gateway
        self.input_guardrails = InputGuardrails(settings)
        self.output_guardrails = OutputGuardrails(settings)
        self.tracing = tracing
        self.prometheus = metrics
        self.cache = cache

    async def process_query(
        self,
        query: str,
        use_cache: bool = True,
        max_contexts: int = 5,
        model: str | None = None,
        tenant: str = "default",
    ) -> "QueryServiceResponse":
        if use_cache:
            cached = await self.cache.get(query)
            if cached is not None:
                try:
                    data = json.loads(cached)
                    return QueryServiceResponse(**data)
                except (json.JSONDecodeError, TypeError):
                    pass

        input_check = await self.input_guardrails.validate(query)
        if input_check.blocked:
            self.prometheus.record_guardrail("input_blocked")
            return QueryServiceResponse(
                content="Votre requête a été bloquée par les garde-fous de sécurité.",
                model="guardrail",
                from_cache=False,
                latency_ms=0,
                tokens_used=0,
                guardrail_triggered=True,
                guardrail_reason=input_check.reason,
            )

        sanitized_query = input_check.sanitized_text or query

        try:
            rag_result = await self.rag.query(
                query=sanitized_query,
                top_k=max_contexts,
                model=model,
            )
        except AllModelsFailedError as e:
            self.prometheus.record_error("all_models_failed")
            return QueryServiceResponse(
                content="Désolé, tous les modèles LLM sont actuellement indisponibles. Veuillez réessayer plus tard.",
                model="none",
                from_cache=False,
                latency_ms=0,
                tokens_used=0,
                error=str(e),
            )

        output_check = await self.output_guardrails.validate(rag_result.content)
        final_content = output_check.sanitized_text or rag_result.content

        trace_id = self.tracing.trace_query(
            query=sanitized_query,
            response=final_content,
            model=rag_result.model,
            latency_ms=rag_result.latency_ms,
            tokens_prompt=rag_result.tokens_prompt,
            tokens_completion=rag_result.tokens_completion,
            tenant=tenant,
            guardrail_triggered=bool(output_check.triggered_rules),
        )

        response = QueryServiceResponse(
            content=final_content,
            model=rag_result.model,
            from_cache=False,
            latency_ms=rag_result.latency_ms,
            tokens_used=rag_result.tokens_prompt + rag_result.tokens_completion,
            contexts=rag_result.contexts,
            guardrail_triggered=bool(output_check.triggered_rules),
            trace_id=trace_id,
        )

        if use_cache:
            from contextlib import suppress

            with suppress(Exception):
                await self.cache.set(query, json.dumps(response.asdict()))

        return response


class QueryServiceResponse:
    def __init__(
        self,
        content: str,
        model: str,
        from_cache: bool,
        latency_ms: int,
        tokens_used: int,
        contexts: list[str] | None = None,
        guardrail_triggered: bool = False,
        guardrail_reason: str | None = None,
        trace_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.content = content
        self.model = model
        self.from_cache = from_cache
        self.latency_ms = latency_ms
        self.tokens_used = tokens_used
        self.contexts = contexts
        self.guardrail_triggered = guardrail_triggered
        self.guardrail_reason = guardrail_reason
        self.trace_id = trace_id
        self.error = error

    def asdict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "model": self.model,
            "from_cache": self.from_cache,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "contexts": self.contexts,
            "guardrail_triggered": self.guardrail_triggered,
            "guardrail_reason": self.guardrail_reason,
            "trace_id": self.trace_id,
            "error": self.error,
        }
