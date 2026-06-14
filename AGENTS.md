# AGENTS.md — GenAI Platform

## Quick start

```bash
make init          # .venv + pip install -e ".[dev,test,eval]" + pre-commit install + run on all files
make build         # all CI gates: lint -> typecheck -> test
make lint          # ruff check src/ tests/
make typecheck     # mypy src/
make test          # pytest tests/ -v --cov=src --cov-report=term-missing
make docker-up     # docker compose up -d (qdrant, redis, postgres, mlflow, langfuse)
```

## Repo quirks

- **Branch name**: `devlop` (not `develop`). CI triggers on `devlop` and `main`.
- **No lockfile**: `pip` only. Builds are not deterministic.
- **No README**: None exists. `.dockerignore` excludes `*.md` except `README.md` (which doesn't exist).
- **LlamaIndex in deps but unused**: RAG pipeline (`rag.py`) uses custom chunking + BM25 + reranker. The dependency is reserved.
- **HybridSearch is BM25-only**: No vector/embedding search yet. Qdrant client is in deps but unused.
- **Mock LLM mode**: When `litellm` not installed, `LLMGateway` returns canned responses. App works without external LLM.
- **Optional services degrade silently**: Presidio, Prometheus, Langfuse each have `try/except ImportError` — app runs without them.
- **Pre-commit mypy vs `make typecheck` mismatch**: Pre-commit runs `mypy --no-strict-optional`; `pyproject.toml` has `strict = true`. `pre-commit run` passes where `make typecheck` may fail.
- **No DB migrations**: No Alembic or migration framework. App has no DB models.
- **`.secrets.baseline`**: Has known false positives for dev-only passwords in `docker-compose.yml`.

## Architecture (quick)

```
genai_platform/
  api.py        — FastAPI app creation (entrypoint: genai_platform.api:app)
  config.py     — pydantic-settings, env prefix GENAI_
  schemas.py    — QueryRequest / QueryResponse
  router.py     — POST /api/v1/query, GET /api/v1/models
  services.py   — QueryService: guardrails -> RAG -> guardrails -> tracing
  gateway.py    — LLMGateway (LiteLLM, fallback chain, circuit breaker per model)
  rag.py        — RAGPipeline (chunking, BM25, reranker, prompt)
  guardrails.py — InputGuardrails / OutputGuardrails (prompt injection, toxicity, PII)
  monitoring.py — MetricsCollector (Langfuse) + PrometheusMetrics
```

## Testing

- **pytest + pytest-asyncio** (`asyncio_mode = auto`)
- Tests in `tests/`, files named `test_*.py`
- `make test-integration` exists but no tests have `@pytest.mark.integration` yet
- No external services required for current tests (mock everything)

## CI pipeline (`.github/workflows/ci.yml`)

Order: `lint` → `test` (3.11 + 3.12 matrix) → `security` (detect-secrets + pip-audit) → `docker` (build + Trivy scan)

## Docs

12 architecture layers in `docs/couche-*.md` (French), 4 ADRs in `docs/adr/`.
