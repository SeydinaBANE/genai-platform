from typing import Protocol


class TracingPort(Protocol):
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
    ) -> str | None: ...

    def score_feedback(self, trace_id: str, rating: float, comment: str | None = None) -> None: ...
