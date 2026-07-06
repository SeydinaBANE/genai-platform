import time

from genai_platform.domain.models import LLMResponse


class LiteLLMProvider:
    async def complete(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        request_timeout: int,
    ) -> LLMResponse:
        from litellm import acompletion

        start = time.time()
        response = await acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=request_timeout,
        )
        latency_ms = int((time.time() - start) * 1000)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            latency_ms=latency_ms,
            tokens_prompt=response.usage.prompt_tokens,
            tokens_completion=response.usage.completion_tokens,
        )

    async def embed(self, model: str, text: str) -> list[float]:
        from litellm import aembedding

        response = await aembedding(model=model, input=[text])
        return response.data[0]["embedding"]  # type: ignore[no-any-return]
