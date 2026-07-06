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
- **RAG is Qdrant vector search, not BM25**: `application/rag_pipeline.py` embeds via `LLMProviderPort` and searches via `VectorStorePort` (Qdrant). LlamaIndex is still an unused reserved dependency.
- **Mock LLM mode**: When `litellm` isn't importable, `bootstrap.py` picks `MockLLMProvider`, which returns canned responses. App works without external LLM.
- **Optional services degrade silently**: Presidio, Prometheus, Langfuse each have `try/except ImportError` — app runs without them.
- **Pre-commit mypy vs `make typecheck` mismatch**: Pre-commit runs `mypy --no-strict-optional`; `pyproject.toml` has `strict = true`. `pre-commit run` passes where `make typecheck` may fail.
- **No DB migrations**: No Alembic or migration framework. App has no DB models.
- **`.secrets.baseline`**: Has known false positives for dev-only passwords in `docker-compose.yml`.

## Architecture (quick)

Hexagonal (ports & adapters) — see `CLAUDE.md` for the full breakdown.

```
genai_platform/
  domain/       — pure logic: value objects, ChunkingStrategy, Reranker, CircuitBreaker, RateLimiter
  ports/        — Protocol interfaces: LLMProviderPort, VectorStorePort, CachePort, TracingPort, MetricsPort
  adapters/     — concrete implementations (llm/, vector_store/, cache/, tracing/, metrics/) + adapters/http/ (FastAPI)
  application/  — use cases: LLMGateway, RAGPipeline, InputGuardrails/OutputGuardrails, QueryService
  bootstrap.py  — composition root (entrypoint: genai_platform.adapters.http.api:app)
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
