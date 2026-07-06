from genai_platform.config import Settings
from genai_platform.domain.circuit_breaker import CircuitBreaker, CircuitBreakerState
from genai_platform.domain.models import LLMResponse
from genai_platform.ports.llm_provider import LLMProviderPort


class LLMGateway:
    def __init__(self, settings: Settings, llm_provider: LLMProviderPort) -> None:
        self.settings = settings
        self.llm_provider = llm_provider
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
        return await self.llm_provider.complete(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=self.settings.llm_request_timeout,
        )


class AllModelsFailedError(Exception):
    def __init__(self, message: str, errors: list[tuple[str, str]]) -> None:
        super().__init__(message)
        self.errors = errors
