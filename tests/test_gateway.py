from unittest.mock import AsyncMock

import pytest

from genai_platform.config import Settings
from genai_platform.gateway import (
    AllModelsFailedError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    LLMGateway,
    LLMResponse,
)

MOCK_RESPONSE = LLMResponse(
    content="mock response",
    model="gpt-4o",
    latency_ms=10,
    tokens_prompt=5,
    tokens_completion=10,
)


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        async def success() -> str:
            return "ok"

        result = await cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

        async def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.CLOSED

        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_state_rejects_calls(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)

        async def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(fail)

    @pytest.mark.asyncio
    async def test_half_open_transitions_to_closed_on_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)

        async def fail() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(fail)
        assert cb.state == CircuitBreakerState.OPEN

        import asyncio

        await asyncio.sleep(0.01)

        async def success() -> str:
            return "ok"

        result = await cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED


class TestLLMGateway:
    def test_init_creates_circuit_breakers(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings)
        assert gateway.default_model == settings.llm_default_model
        assert len(gateway.circuit_breakers) == 1 + len(settings.llm_fallback_models)

    @pytest.mark.asyncio
    async def test_complete_returns_response(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings)
        gateway._do_llm_call = AsyncMock(return_value=MOCK_RESPONSE)  # type: ignore[method-assign]
        result = await gateway.complete(prompt="Hello")
        assert isinstance(result, LLMResponse)
        assert result.content == "mock response"
        assert result.from_fallback is False

    @pytest.mark.asyncio
    async def test_complete_uses_custom_model(self) -> None:
        settings = Settings()
        gateway = LLMGateway(settings)
        gateway._do_llm_call = AsyncMock(return_value=MOCK_RESPONSE)  # type: ignore[method-assign]
        result = await gateway.complete(prompt="Hello", model="gpt-4o")
        assert result.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_fallback_on_failure(self) -> None:
        settings = Settings(llm_fallback_models=["fallback-model"])
        custom = LLMResponse(
            content="fallback ok",
            model="fallback-model",
            latency_ms=10,
            tokens_prompt=5,
            tokens_completion=10,
        )
        gateway = LLMGateway(settings)
        gateway._do_llm_call = AsyncMock(return_value=custom)  # type: ignore[method-assign]
        result = await gateway.complete(prompt="Hello")
        assert result.content == "fallback ok"

    @pytest.mark.asyncio
    async def test_complete_raises_all_models_failed(self) -> None:
        settings = Settings(llm_fallback_models=[])
        gateway = LLMGateway(settings)
        gateway._do_llm_call = AsyncMock(side_effect=ValueError("API error"))  # type: ignore[method-assign]
        with pytest.raises(AllModelsFailedError):
            await gateway.complete(prompt="Hello")

    @pytest.mark.asyncio
    async def test_complete_skips_open_circuit_breaker(self) -> None:
        settings = Settings(llm_fallback_models=["fallback-model"])
        gateway = LLMGateway(settings)
        gateway._do_llm_call = AsyncMock(return_value=MOCK_RESPONSE)  # type: ignore[method-assign]

        cb = gateway.circuit_breakers[settings.llm_default_model]
        cb.state = CircuitBreakerState.OPEN
        cb.last_failure_time = 9999999999.0

        result = await gateway.complete(prompt="Hello")
        assert result.content == "mock response"
        assert result.model == "gpt-4o"
