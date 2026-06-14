# Couche 6 — Monitoring & Observabilité

## Objectif
Tracer, mesurer et alerter sur chaque aspect de la plateforme : latence, coût, qualité, erreurs, drift.

## Stack
- **Tracing LLM** : LangFuse (traces, spans, scores)
- **Métriques** : Prometheus + Grafana
- **Drift Detection** : embedding drift + response drift + concept drift
- **Alerting** : PagerDuty + Slack
- **Logging** : structuré (JSON) via ELK / Loki

## Architecture

```
[Application] → [LangFuse SDK] → [LangFuse API] → [Dashboard]
                                           ↓
[Prometheus] ← [Metrics Exporter] ← [Gateway] ← [RAG] ← [Guardrails]
      ↓
[Grafana] → [Alertmanager] → [Slack / PagerDuty]
```

## Tracing — LangFuse

```python
from langfuse.decorators import observe, langfuse_context
from langfuse import Langfuse

class GenAITracer:
    def __init__(self):
        self.langfuse = Langfuse()

    @observe(name="rag_query")
    async def trace_query(self, query: str, tenant: str):
        langfuse_context.update_current_trace(
            user_id=tenant,
            session_id=self._get_or_create_session(tenant),
            metadata={"app_version": __version__},
        )

        # scores stockés dans LangFuse
        langfuse_context.score_current_trace(
            name="user_feedback",
            value=0.9,
        )

    @observe(name="llm_call")
    async def trace_llm_call(self, model: str, prompt_tokens: int, completion_tokens: int):
        langfuse_context.update_current_observation(
            input=prompt_tokens,
            output=completion_tokens,
            model=model,
            metadata={
                "cost": self._compute_cost(model, prompt_tokens, completion_tokens),
                "latency_ms": langfuse_context.get_current_observation().latency,
            },
        )
```

## Métriques Prometheus

```python
from prometheus_client import Histogram, Counter, Gauge, Summary

# Latence
LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM request latency",
    ["model", "operation", "tenant"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

RAG_LATENCY = Histogram(
    "rag_pipeline_duration_seconds",
    "RAG pipeline total latency",
    ["operation"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# Coût
LLM_COST = Counter(
    "llm_cost_total",
    "Total LLM cost in USD",
    ["model", "tenant", "operation"],
)

# Qualité
QUALITY_SCORE = Gauge(
    "rag_quality_score",
    "RAG quality score (RAGAS composite)",
    ["tenant"],
)

# Cache
CACHE_HIT_RATIO = Gauge(
    "cache_hit_ratio",
    "Semantic cache hit ratio",
    ["cache_type"],
)

# Erreurs
LLM_ERRORS = Counter(
    "llm_errors_total",
    "Total LLM errors",
    ["model", "error_type", "tenant"],
)
```

## Drift Detection

```python
class DriftDetector:
    def __init__(self, redis_client, qdrant_client):
        self.redis = redis_client
        self.qdrant = qdrant_client

    async def check_embedding_drift(self, collection: str, window_hours: int = 24) -> float:
        recent = await self._get_recent_embeddings(collection, window_hours)
        baseline = await self._get_baseline_embeddings(collection)

        drift = 1.0 - cosine_similarity(
            np.mean(recent, axis=0).reshape(1, -1),
            np.mean(baseline, axis=0).reshape(1, -1),
        )[0][0]

        if drift > self.config.drift_threshold:
            await self._alert_drift(collection, drift)

        return drift

    async def check_response_drift(self, tenant: str, window: int = 100) -> dict:
        recent_responses = await self._get_recent_responses(tenant, window)
        metrics = self._compute_response_metrics(recent_responses)

        return {
            "avg_length": metrics["avg_length"],
            "avg_sentiment": metrics["avg_sentiment"],
            "refusal_rate": metrics["refusal_rate"],
            "language_distribution": metrics["language_dist"],
            "drift_detected": any(v > self.config.drift_threshold for v in metrics.values()),
        }
```

## Alerting Rules

```yaml
# prometheus-rules.yaml
groups:
  - name: genai-platform
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.99, llm_request_duration_seconds) > 10
        for: 5m
        labels: { severity: critical }
        annotations:
          summary: "P99 latency > 10s for {{ $labels.model }}"

      - alert: HighCost
        expr: rate(llm_cost_total[1h]) > 100
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "Cost rate > $100/h for {{ $labels.tenant }}"

      - alert: LowQuality
        expr: rag_quality_score < 0.7
        for: 15m
        labels: { severity: critical }
        annotations:
          summary: "Quality score < 0.7 for {{ $labels.tenant }}"

      - alert: HighErrorRate
        expr: rate(llm_errors_total[5m]) / rate(llm_requests_total[5m]) > 0.05
        for: 5m
        labels: { severity: critical }
        annotations:
          summary: "Error rate > 5% for {{ $labels.model }}"

      - alert: NoTraffic
        expr: rate(llm_requests_total[10m]) == 0
        for: 10m
        labels: { severity: warning }
        annotations:
          summary: "No traffic — possible outage"
```

## Dashboards Grafana

| Dashboard | Métriques clés |
|---|---|
| **LLM Performance** | Latence P50/P95/P99, tokens/s, erreurs par type |
| **Cost Analysis** | Coût par modèle, par tenant, par jour, projection |
| **Quality Overview** | RAGAS scores, feedback utilisateur, drift |
| **Cache Efficiency** | Hit ratio, taille, économies estimées |
| **Tenant Health** | Rate limit, budget, qualité par tenant |

## Pièges à éviter
- ❌ Pas de sampling → explosion de coût de stockage des traces
- ❌ Alerting trop sensible → fatigue des on-call
- ❌ Metrics sans labels tenant → impossible de debugger par client
- ❌ Pas de baseline → impossible de détecter le drift
- ❌ Logs non structurés → impossible de chercher
