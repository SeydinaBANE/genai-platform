from typing import Any


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
