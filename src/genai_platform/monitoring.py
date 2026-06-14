from typing import Any

from genai_platform.config import Settings


class MetricsCollector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._langfuse: Any = None

    @property
    def langfuse(self) -> Any:
        if self._langfuse is None:
            self._langfuse = self._init_langfuse()
        return self._langfuse

    def _init_langfuse(self) -> Any:
        if not self.settings.langfuse_public_key:
            return None
        try:
            from langfuse import Langfuse

            return Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
        except ImportError:
            return None

    def trace_query(
        self,
        query: str,
        response: str,
        model: str,
        latency_ms: int,
        tokens_prompt: int,
        tokens_completion: int,
        tenant: str = "default",
        guardrail_triggered: bool = False,
    ) -> str | None:
        if not self.langfuse:
            return None

        trace = self.langfuse.trace(
            name="rag_query",
            user_id=tenant,
            metadata={
                "model": model,
                "latency_ms": latency_ms,
                "tokens_total": tokens_prompt + tokens_completion,
                "guardrail_triggered": guardrail_triggered,
            },
        )

        trace.generation(
            name="llm_call",
            model=model,
            input=query,
            output=response,
            usage={
                "input": tokens_prompt,
                "output": tokens_completion,
            },
        )

        return trace.id  # type: ignore[no-any-return]

    def score_feedback(self, trace_id: str, rating: float, comment: str | None = None) -> None:
        if not self.langfuse or not trace_id:
            return
        self.langfuse.score(
            trace_id=trace_id,
            name="user_rating",
            value=rating,
            comment=comment,
        )


class PrometheusMetrics:
    def __init__(self) -> None:
        self._initialized = False
        self._metrics: dict[str, Any] = {}

    def init(self) -> None:
        if self._initialized:
            return
        try:
            from prometheus_client import Counter, Histogram

            self._metrics["requests_total"] = Counter(
                "rag_requests_total",
                "Total RAG queries",
                ["model", "tenant"],
            )
            self._metrics["latency"] = Histogram(
                "rag_latency_seconds",
                "RAG query latency",
                ["model"],
                buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
            )
            self._metrics["tokens_total"] = Counter(
                "rag_tokens_total",
                "Total tokens used",
                ["model", "type"],
            )
            self._metrics["errors_total"] = Counter(
                "rag_errors_total",
                "Total errors",
                ["error_type", "model"],
            )
            self._metrics["guardrail_triggers"] = Counter(
                "rag_guardrail_triggers",
                "Guardrail triggers",
                ["rule"],
            )
            self._initialized = True
        except ImportError:
            pass

    def record_request(self, model: str, tenant: str = "default") -> None:
        if not self._initialized:
            return
        self._metrics["requests_total"].labels(model=model, tenant=tenant).inc()

    def record_latency(self, model: str, seconds: float) -> None:
        if not self._initialized:
            return
        self._metrics["latency"].labels(model=model).observe(seconds)

    def record_tokens(self, model: str, token_type: str, count: int) -> None:
        if not self._initialized:
            return
        self._metrics["tokens_total"].labels(model=model, type=token_type).inc(count)

    def record_error(self, error_type: str, model: str = "unknown") -> None:
        if not self._initialized:
            return
        self._metrics["errors_total"].labels(error_type=error_type, model=model).inc()

    def record_guardrail(self, rule: str) -> None:
        if not self._initialized:
            return
        self._metrics["guardrail_triggers"].labels(rule=rule).inc()
