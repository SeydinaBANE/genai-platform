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

FastAPI app defined in `src/genai_platform/api.py` (entrypoint `genai_platform.api:app`). All app-wide singletons (`Settings`, `LLMGateway`, `RAGPipeline`, `QueryService`, `RateLimiter`) are constructed once in the `lifespan` context and stored on `app.state`; request handlers reach them via `dependencies.py` (`get_settings`, `get_query_service`), never by importing globals.

Request flow for `POST /api/v1/query` (`router.py` -> `services.py`):
1. `RateLimiter` middleware (per-client-IP token bucket, RPM+TPM) runs before routing, except for `/metrics`.
2. `verify_api_key` dependency checks `X-API-Key` header against `settings.api_keys` (auth is a no-op if `api_keys` is empty — README's mention of an `Authorization` header is stale, the real header is `X-API-Key`).
3. `QueryService.process_query` (`services.py`): semantic cache lookup (Redis, keyed by SHA-256 of the raw query) -> `InputGuardrails.validate` -> `RAGPipeline.query` -> `OutputGuardrails.validate` -> `MetricsCollector.trace_query` (Langfuse) -> cache write.
4. `RAGPipeline.query` (`rag.py`) embeds the query, does a Qdrant vector search, reranks with `Reranker`, builds a French-language grounded prompt, and calls `LLMGateway.complete`.
5. `LLMGateway.complete` (`gateway.py`) tries the requested model then each fallback model in order, gated by a per-model `CircuitBreaker` (closed/open/half-open), and raises `AllModelsFailedError` if everything fails.

Key point: every optional dependency degrades gracefully instead of failing:
- `litellm` not installed -> `LLMGateway` and embeddings return deterministic mock responses (app fully usable without any real LLM).
- `qdrant-client` unavailable/collection not ready -> `RAGPipeline.query` returns a static "no documents found" result instead of erroring.
- `presidio_analyzer`/`presidio_anonymizer` not installed -> PII checks in `guardrails.py` silently no-op.
- `langfuse` not configured (no public key) or not installed -> `MetricsCollector` traces are skipped.
- `prometheus_client` not installed -> `PrometheusMetrics` methods no-op.
- `redis` not installed/unreachable -> `SemanticCache` no-ops (cache miss, no error).

Guardrails (`guardrails.py`) are not ML-based: prompt injection and toxicity detection are regex/keyword matching (`InputGuardrails._check_prompt_injection`, `_check_toxicity`); only PII detection actually uses a model (Presidio), and only when installed.

Config (`config.py`) is a single `pydantic-settings` `Settings` class, env prefix `GENAI_`, loaded from `.env`. All tunables (chunk size, RPM/TPM, circuit breaker thresholds, model names) live there — don't hardcode them elsewhere.

## Repo quirks worth knowing

- Branch is `devlop`, not `develop`. CI (`.github/workflows/ci.yml`) triggers on push to `devlop`/`main` and PRs into `main`.
- CI job graph: `lint` runs first; `test` and `security` both run in parallel after `lint` passes; `docker` (build + Trivy scan) needs both `lint` and `test`.
- Pre-commit's mypy hook runs with `--ignore-missing-imports --no-strict-optional` (`.pre-commit-config.yaml`), while `pyproject.toml` sets `strict = true` for `make typecheck`. `pre-commit run` can pass while `make typecheck` fails — always run `make typecheck` before considering a change done, not just pre-commit.
- `qdrant-client` and `litellm` are real runtime dependencies (not just reserved) — `RAGPipeline` and `LLMGateway` use them directly when available, falling back to mocks only on `ImportError`.
- `.secrets.baseline` has known false positives for dev-only passwords in `docker-compose.yml`.
- `make test-integration` exists but no test currently carries `@pytest.mark.integration`.
- 12-layer architecture is documented in French in `docs/couche-*.md`; architecture decisions are in `docs/adr/*.md`.
