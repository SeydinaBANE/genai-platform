# Couche 3 — LLM Gateway

## Objectif
Proxy unifié vers tous les fournisseurs LLM avec rate limiting, caching, fallback et observabilité.

## Stack
- **Gateway** : LiteLLM (proxy HTTP)
- **Cache sémantique** : GPTCache + Redis
- **Fallback chain** : multi-modèles
- **Circuit breaker** : stopper les appels après N erreurs consécutives
- **Rate limiter** : sliding window per tenant

## Architecture

```
[Application] → LiteLLM → [Rate Limiter] → [Circuit Breaker] → [Semantic Cache]
                ↓                            ↓                       ↓
          [Anthropic/GPT/Claude]       [Open Source]           [Cache Hit]
                ↓                            ↓                       ↓
          [Response]                   [Response]              [Return Fast]
```

## Configuration Gateway

```yaml
# config/gateway.yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      rpm: 1000
      tpm: 100000
    fallbacks:
      - claude-3-sonnet
      - mistral-large

  - model_name: claude-3-sonnet
    litellm_params:
      model: anthropic/claude-3-sonnet-20240229
      api_key: os.environ/ANTHROPIC_API_KEY
      rpm: 500

  - model_name: mistral-large
    litellm_params:
      model: mistral/mistral-large-latest
      api_key: os.environ/MISTRAL_API_KEY
      rpm: 2000

router_settings:
    routing_strategy: "latency-based"
    num_retries: 3
    request_timeout: 30
    fallback_strategy: "immediately"
    redis_host: redis
    redis_port: 6379
    redis_password: os.environ/REDIS_PASSWORD
```

## Bonnes pratiques senior — Gateway

```python
class GatewayConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GENAI_", env_file=".env")

    openai_api_key: SecretStr
    anthropic_api_key: SecretStr

    gateway_host: str = "0.0.0.0"
    gateway_port: int = 4000

    rate_limit_rpm: int = 1000
    rate_limit_tpm: int = 100_000

    cache_ttl: int = 3600
    cache_similarity_threshold: float = 0.92

    circuit_breaker_failures: int = 5
    circuit_breaker_timeout: int = 60

    fallback_order: list[str] = ["gpt-4o", "claude-3-sonnet", "mistral-large"]
```

Règles :
- **Fallback toujours configuré** : si GPT tombe, basculer automatiquement
- **Capacité par modèle** : RPM/TPM explicites pour éviter le rate limiting du fournisseur
- **Circuit breaker** : 5 échecs consécutifs → pause 60s
- **Cache sémantique** : similarité cosine > 0.92 → cache hit (~40% hit rate)
- **Timeout** : 30s max, un LLM qui dépasse est un LLM mort

## Monitoring

```yaml
metrics:
  - name: llm_latency_seconds
    type: histogram
    labels: [model, tenant, operation]
  - name: llm_cost_total
    type: counter
    labels: [model, tenant]
  - name: llm_cache_hit_ratio
    type: gauge
  - name: llm_fallback_count
    type: counter
    labels: [from_model, to_model]
  - name: llm_errors_total
    type: counter
    labels: [model, error_type]
```

## Runbook
```bash
curl http://gateway:4000/health
curl http://gateway:4000/models
curl -X POST http://gateway:4000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Pièges à éviter
- ❌ Pas de fallback → un provider down = application down
- ❌ Cache illimité → explosion mémoire, TTL obligatoire
- ❌ Pas de circuit breaker → cascade failures
- ❌ Rate limiting trop laxiste → facture surprise
- ❌ Clés API en clair dans le code
