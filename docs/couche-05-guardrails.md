# Couche 5 — Guardrails

## Objectif
Sécuriser les entrées et sorties du LLM : prévenir les injections, les fuites de données, les contenus toxiques et les hallucinations dangereuses.

## Stack
- **Framework** : Guardrails AI
- **PII Detection** : Microsoft Presidio
- **Content Moderation** : OpenAI moderation API / custom classifier
- **Prompt Injection** : detector basé sur perplexité + regex
- **Cost Caps** : rate limiting + budget par tenant

## Architecture

```
[User Input] → [Input Guardrails]
                   ├── Prompt injection detection
                   ├── PII scanning
                   ├── Topic filtering
                   ├── Length / cost estimation
                   ├── Rate limit check
                   └── Block if unsafe → [Error response]

                        ↓
                   [LLM Call]

                        ↓
[Output Guardrails]
    ├── PII leakage detection
    ├── Toxicity / bias check
    ├── Factual consistency
    ├── Format validation (JSON, XML, etc.)
    ├── Token budget check
    └── Block if unsafe → [Fallback response]

         ↓
   [Final Response]
```

## Configuration Guardrails

```python
from guardrails import Guard
from guardrails.hub import (
    ToxicLanguage,
    PIIFilter,
    RegexMatch,
    ValidJSON,
    HallucinationDetector,
)

class InputGuardrails:
    guard = Guard().use_many(
        PIIFilter(
            pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "SSN"],
            on_fail="fix",
        ),
        ToxicLanguage(
            threshold=0.7,
            validation_method="sentence",
            on_fail="exception",
        ),
        RegexMatch(
            regex=r"^(?!.*(?:ignore previous|system prompt|you are ai)).*$",
            on_fail="exception",
        ),
    )

    async def validate(self, user_input: str) -> GuardOutput:
        return await self.guard.validate(user_input)

class OutputGuardrails:
    guard = Guard().use_many(
        PIIFilter(
            pii_entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"],
            on_fail="fix",
        ),
        ToxicLanguage(threshold=0.5, on_fail="exception"),
        ValidJSON(on_fail="exception"),
    )

    async def validate(self, llm_output: str) -> GuardOutput:
        return await self.guard.validate(llm_output)
```

## Rate Limiting & Cost Caps

```python
class TenantRateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def check(self, tenant_id: str) -> RateLimitResult:
        pipe = self.redis.pipeline()
        now = int(time.time())
        window = 60

        pipe.zremrangebyscore(f"ratelimit:{tenant_id}", 0, now - window)
        pipe.zcard(f"ratelimit:{tenant_id}")
        pipe.zadd(f"ratelimit:{tenant_id}", {str(now): now})
        pipe.expire(f"ratelimit:{tenant_id}", window)
        _, count, _, _ = await pipe.execute()

        return RateLimitResult(
            allowed=count < self.config.rate_limit_rpm,
            remaining=self.config.rate_limit_rpm - count,
            reset_at=now + window,
        )

    async def check_budget(self, tenant_id: str, cost: float) -> bool:
        total = await self.redis.get(f"budget:{tenant_id}:monthly") or 0
        return float(total) + cost < self.config.monthly_budget[tenant_id]
```

## PII Detection (Presidio)

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

class PIIManager:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    async def analyze(self, text: str) -> list[dict]:
        results = self.analyzer.analyze(
            text=text,
            entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "SSN", "PERSON"],
            language="fr",
            score_threshold=0.6,
        )
        return [
            {"entity": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
            for r in results
        ]

    async def anonymize(self, text: str) -> str:
        result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=self.analyzer.analyze(text, language="fr"),
            operators={"DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"})},
        )
        return result.text
```

## Production thresholds

| Garde-fou | Action | Seuil |
|---|---|---|
| Injection prompt | Bloquer + log + alert | Score > 0.8 |
| PII en entrée | Anonymiser | Tout |
| PII en sortie | Anonymiser + audit | Tout |
| Toxicité | Bloquer | Score > 0.7 |
| Budget mensuel | Bloquer | Dépassé |
| Rate limit | 429 Too Many Requests | Dépassé |

## Pièges à éviter
- ❌ Guardrails en entrée mais pas en sortie → fuite PII
- ❌ Threshold trop bas → faux positifs qui bloquent des requêtes légitimes
- ❌ Pas de log des guardrails déclenchés → impossible d'auditer
- ❌ Rate limiting global (pas par tenant) → un tenant bruyant pourrit tout le monde
