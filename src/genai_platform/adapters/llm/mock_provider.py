import asyncio
import time

from genai_platform.domain.embeddings import mock_embedding
from genai_platform.domain.models import LLMResponse


class MockLLMProvider:
    async def complete(
        self,
        model: str,
        prompt: str,
        temperature: float,  # noqa: ARG002
        max_tokens: int,  # noqa: ARG002
        request_timeout: int,  # noqa: ARG002
    ) -> LLMResponse:
        start = time.time()
        await asyncio.sleep(0.05)
        latency_ms = int((time.time() - start) * 1000)

        return LLMResponse(
            content=f"[{model}] Réponse simulée pour : {prompt[:50]}...",
            model=model,
            latency_ms=latency_ms,
            tokens_prompt=10,
            tokens_completion=20,
        )

    async def embed(self, model: str, text: str) -> list[float]:  # noqa: ARG002
        return mock_embedding(text)
