import asyncio
import time

from genai_platform.config import Settings
from genai_platform.domain.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)
from genai_platform.domain.models import LLMResponse

__all__ = [
    "AllModelsFailedError",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitBreakerState",
    "LLMGateway",
    "LLMResponse",
    "MockLLMResponse",
]


class LLMGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.default_model = settings.llm_default_model
        self.fallback_models = settings.llm_fallback_models
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self._init_circuit_breakers()

    def _init_circuit_breakers(self) -> None:
        models = [self.default_model, *self.fallback_models]
        for model in models:
            self.circuit_breakers[model] = CircuitBreaker(
                failure_threshold=self.settings.circuit_breaker_failures,
                recovery_timeout=self.settings.circuit_breaker_timeout,
            )

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        model = model or self.default_model
        temperature = temperature if temperature is not None else self.settings.llm_temperature
        max_tokens = max_tokens or self.settings.llm_max_tokens

        errors: list[tuple[str, str]] = []
        models_to_try = [model] + [m for m in self.fallback_models if m != model]

        for attempt_model in models_to_try:
            cb = self.circuit_breakers.get(attempt_model)
            if cb and cb.state == CircuitBreakerState.OPEN:
                errors.append((attempt_model, "circuit breaker open"))
                continue

            try:
                result = await self._call_llm(attempt_model, prompt, temperature, max_tokens)
                result.from_fallback = attempt_model != model
                return result
            except Exception as e:
                errors.append((attempt_model, str(e)))

        raise AllModelsFailedError(
            f"All LLM models failed: {errors}",
            errors,
        )

    async def _call_llm(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        cb = self.circuit_breakers.get(model)
        if cb:
            result = await cb.call(self._do_llm_call, model, prompt, temperature, max_tokens)
            return result  # type: ignore[no-any-return]
        return await self._do_llm_call(model, prompt, temperature, max_tokens)

    async def _do_llm_call(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        start = time.time()

        try:
            from litellm import acompletion

            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=self.settings.llm_request_timeout,
            )
        except ImportError:
            response = await self._mock_llm_call(model, prompt)

        latency_ms = int((time.time() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            latency_ms=latency_ms,
            tokens_prompt=response.usage.prompt_tokens,
            tokens_completion=response.usage.completion_tokens,
        )

    async def _mock_llm_call(self, model: str, prompt: str) -> "MockLLMResponse":
        await asyncio.sleep(0.05)
        return MockLLMResponse(
            content=f"[{model}] Réponse simulée pour : {prompt[:50]}...",
            model=model,
        )


class AllModelsFailedError(Exception):
    def __init__(self, message: str, errors: list[tuple[str, str]]) -> None:
        super().__init__(message)
        self.errors = errors


class MockLLMResponse:
    class Choice:
        class Message:
            def __init__(self, content: str) -> None:
                self.content = content

        def __init__(self, content: str) -> None:
            self.message = self.Message(content)

    class Usage:
        def __init__(self) -> None:
            self.prompt_tokens = 10
            self.completion_tokens = 20

    def __init__(self, content: str, model: str) -> None:
        self.choices = [self.Choice(content)]
        self.usage = self.Usage()
        self.model = model
