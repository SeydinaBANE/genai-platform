from typing import Protocol

from genai_platform.domain.models import LLMResponse


class LLMProviderPort(Protocol):
    async def complete(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        request_timeout: int,
    ) -> LLMResponse: ...

    async def embed(self, model: str, text: str) -> list[float]: ...
