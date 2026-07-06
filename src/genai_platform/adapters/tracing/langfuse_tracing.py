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
