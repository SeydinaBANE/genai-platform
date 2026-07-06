# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make init              # .venv + pip install -e ".[dev,test,eval]" + pre-commit install + run on all files
make lint              # ruff check src/ tests/
make lint-fix          # ruff check --fix src/ tests/
make format            # ruff format src/ tests/
make typecheck         # mypy src/ (strict = true)
make test              # pytest tests/ -v --cov=src --cov-report=term-missing
make test-coverage     # same, with HTML coverage report
make build             # lint -> typecheck -> test (what CI enforces)
make security          # detect-secrets scan --baseline .secrets.baseline && pip-audit
make docker-up         # qdrant + redis + postgres + mlflow + langfuse via docker compose
make docker-down       # stop stack and remove volumes
```

Single test: `pytest tests/test_rag.py::test_name -v` (asyncio_mode is `auto`, no `@pytest.mark.asyncio` needed).

There is no lockfile (pip only, no uv/poetry) and no DB migration framework (no models to migrate).

## Architecture

Hexagonal (ports & adapters). `src/genai_platform/` is organized in four layers:

- `domain/` — pure, framework-free logic: value objects (`models.py`: `Chunk`, `Document`, `ScoredChunk`, `RAGResult`, `LLMResponse`, `GuardrailResult`), `ChunkingStrategy`, `Reranker`, `CircuitBreaker`, mock embedding generation, guardrail regex rules, `RateLimiter`/`TokenBucket`.
- `ports/` — `typing.Protocol` interfaces for every swappable external system: `LLMProviderPort`, `VectorStorePort`, `CachePort`, `TracingPort`, `MetricsPort`.
- `adapters/` — concrete implementations of those ports, plus the FastAPI HTTP layer (`adapters/http/`) as the driving/primary adapter:
  - `adapters/llm/`: `LiteLLMProvider` (real) and `MockLLMProvider` (canned responses, used when `litellm` isn't importable).
  - `adapters/vector_store/qdrant_store.py`: `QdrantVectorStore`.
  - `adapters/cache/redis_cache.py`: `SemanticCache` (exact-match despite the name, keyed by SHA-256 of the raw query).
  - `adapters/tracing/langfuse_tracing.py`: `MetricsCollector` (Langfuse).
  - `adapters/metrics/prometheus_metrics.py`: `PrometheusMetrics`.
  - `adapters/http/`: `api.py` (FastAPI app + `lifespan`, entrypoint `genai_platform.adapters.http.api:app`), `router.py`, `auth.py`, `dependencies.py`, `schemas.py` (wire-contract DTOs, distinct from the application-layer `QueryServiceResponse`).
- `application/` — use cases orchestrating domain + ports: `LLMGateway` (circuit breaker + fallback chain over an injected `LLMProviderPort`), `RAGPipeline` (chunk/embed/search/rerank/prompt, over injected `LLMProviderPort` + `VectorStorePort`), `InputGuardrails`/`OutputGuardrails`, `QueryService`.

`bootstrap.py`'s `build_app_components(settings)` is the composition root: it decides `LiteLLMProvider` vs `MockLLMProvider` once (based on whether `litellm` imports), constructs every other adapter, and wires them into the application-layer use cases. `adapters/http/api.py`'s `lifespan` calls it and stores the result on `app.state`; request handlers reach `app.state` via `adapters/http/dependencies.py` (`get_settings`, `get_query_service`), never by importing globals.

The old flat module paths (`gateway.py`, `rag.py`, `guardrails.py`, `cache.py`, `monitoring.py`, `rate_limiter.py`, `services.py` at the top of `src/genai_platform/`) still exist as thin re-export shims over the new locations, kept only so external references don't break during the migration — new code should import from `domain/`, `ports/`, `adapters/`, or `application/` directly, not from the shims.

Request flow for `POST /api/v1/query` (`adapters/http/router.py` -> `application/query_service.py`):
1. `RateLimiter` middleware (per-client-IP token bucket, RPM+TPM) runs before routing, except for `/metrics`.
2. `verify_api_key` dependency checks `X-API-Key` header against `settings.api_keys` (auth is a no-op if `api_keys` is empty — README's mention of an `Authorization` header is stale, the real header is `X-API-Key`).
3. `QueryService.process_query`: semantic cache lookup -> `InputGuardrails.validate` -> `RAGPipeline.query` -> `OutputGuardrails.validate` -> `TracingPort.trace_query` (Langfuse) -> cache write.
4. `RAGPipeline.query` embeds the query via `LLMProviderPort`, searches via `VectorStorePort`, reranks with `Reranker`, builds a French-language grounded prompt, and calls `LLMGateway.complete`.
5. `LLMGateway.complete` tries the requested model then each fallback model in order, gated by a per-model `CircuitBreaker` (closed/open/half-open), delegating the actual call to the injected `LLMProviderPort`, and raises `AllModelsFailedError` if everything fails.

Key point: every optional dependency degrades gracefully instead of failing:
- `litellm` not importable -> `bootstrap.py` picks `MockLLMProvider` for the whole process (deterministic canned responses; app fully usable without any real LLM).
- `qdrant-client` unreachable -> `QdrantVectorStore.ensure_collection` catches the connection failure and sets `ready = False`; `RAGPipeline.query` returns a static "no documents found" result instead of erroring.
- `presidio_analyzer`/`presidio_anonymizer` not installed -> PII checks in `application/guardrails.py` silently no-op (no port for this — see below).
- `langfuse` not configured (no public key) or not installed -> `MetricsCollector` traces are skipped.
- `prometheus_client` not installed -> `PrometheusMetrics` methods no-op.
- `redis` not installed/unreachable -> `SemanticCache` no-ops (cache miss, no error).

Not everything got a port: PII sanitization (Presidio) and rate limiting stay as plain domain/application code with no `Protocol` — neither has a second real implementation or a test double that needs one, so a port would be pure abstraction for its own sake.

Guardrails are not ML-based: prompt injection and toxicity detection are regex/keyword matching (`domain/guardrail_rules.py`); only PII detection actually uses a model (Presidio), and only when installed.

Config (`config.py`) is a single `pydantic-settings` `Settings` class, env prefix `GENAI_`, loaded from `.env`. All tunables (chunk size, RPM/TPM, circuit breaker thresholds, model names) live there — don't hardcode them elsewhere.

## Repo quirks worth knowing

- Branch is `devlop`, not `develop`. CI (`.github/workflows/ci.yml`) triggers on push to `devlop`/`main` and PRs into `main`.
- CI job graph: `lint` runs first; `test` and `security` both run in parallel after `lint` passes; `docker` (build + Trivy scan) needs both `lint` and `test`.
- Pre-commit's mypy hook runs with `--ignore-missing-imports --no-strict-optional` (`.pre-commit-config.yaml`), while `pyproject.toml` sets `strict = true` for `make typecheck`. `pre-commit run` can pass while `make typecheck` fails — always run `make typecheck` before considering a change done, not just pre-commit.
- `qdrant-client` and `litellm` are real runtime dependencies (not just reserved). `qdrant-client` is always used (`QdrantVectorStore`, no import guard); `litellm`'s absence is checked once in `bootstrap.py`, not per-call.
- `.secrets.baseline` has known false positives for dev-only passwords in `docker-compose.yml`.
- `make test-integration` exists but no test currently carries `@pytest.mark.integration`.
- 12-layer architecture is documented in French in `docs/couche-*.md`; architecture decisions are in `docs/adr/*.md`.
