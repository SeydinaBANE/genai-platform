# Couche 10 — Tests

## Objectif
Assurer la qualité du code et des réponses LLM via une pyramid de tests adaptée à la GenAI.

## Pyramide des tests GenAI

```
                ⬆ Adversarial
               ⬆⬆ Regression prompts
              ⬆⬆⬆ Integration / E2E
             ⬆⬆⬆⬆ Eval (RAGAS)
            ⬆⬆⬆⬆⬆ Component
           ⬆⬆⬆⬆⬆⬆ Unit tests
```

## Tests Unitaires

```python
# tests/test_chunking.py
def test_semantic_chunking_respects_max_tokens():
    chunker = SemanticChunker(max_chunk_size=512, overlap=0.1)
    text = "Long document text..." * 100
    chunks = chunker.chunk_document(text)
    for chunk in chunks:
        assert len(chunk.tokens) <= 512

def test_chunking_with_overlap():
    chunker = SemanticChunker(max_chunk_size=100, overlap=0.15)
    text = "A. " * 50 + "B. " * 50 + "C. " * 50
    chunks = chunker.chunk_document(text)
    for i in range(len(chunks) - 1):
        assert chunks[i].text[-15:] == chunks[i + 1].text[:15]

def test_chunking_preserves_metadata():
    chunker = SemanticChunker(max_chunk_size=512)
    doc = Document(text="Content", metadata={"source": "report.pdf", "page": 5})
    chunks = chunker.chunk_document(doc)
    for chunk in chunks:
        assert chunk.metadata["source"] == "report.pdf"
        assert chunk.metadata["page"] == 5
```

## Tests de Composant

```python
# tests/test_gateway.py
@pytest.mark.asyncio
async def test_gateway_fallback_on_model_failure():
    gateway = Gateway(models=[mock_gpt, mock_claude])
    mock_gpt.set_fail(True)
    response = await gateway.chat("Hello", model="gpt-4o")
    assert response.model == "claude-3-sonnet"  # fallback

@pytest.mark.asyncio
async def test_gateway_circuit_breaker():
    gateway = Gateway(circuit_breaker_failures=3)
    for _ in range(3):
        with pytest.raises(CircuitBreakerOpen):
            await gateway.chat("Hello")
    with pytest.raises(CircuitBreakerOpen):
        await gateway.chat("Hello")

@pytest.mark.asyncio
async def test_semantic_cache_hit():
    cache = SemanticCache(similarity_threshold=0.95)
    query = "What is RAG?"
    response = "RAG is Retrieval Augmented Generation"
    await cache.set(query, response)
    similar = "Explain RAG to me"
    cached = await cache.get(similar)
    assert cached == response
```

## Tests de Regression Prompts

```python
# tests/eval/test_prompt_regression.py
class TestPromptRegression:
    """
    Ces tests s'assurent que les modifications de prompts
    n'introduisent pas de régression. Exécuté en CI.
    """
    @pytest.mark.parametrize("scenario", [
        "question_simple",
        "question_complexe",
        "question_technique",
        "question_ambigue",
        "refus_harmful",
        "extraction_donnees",
    ])
    async def test_prompt_regression(self, scenario: str):
        dataset = self.load_dataset(scenario)

        for sample in dataset:
            response = await self.pipeline.query(sample.query)
            assert response.quality >= sample.baseline_quality - 0.05
            assert response.faithfulness >= sample.baseline_faithfulness - 0.05

    async def test_no_pii_leakage(self):
        dataset = self.load_dataset("pii_test")
        for sample in dataset:
            response = await self.pipeline.query(sample.query)
            assert not contains_pii(response.content)
```

## Tests Adversariaux

```python
# tests/eval/test_adversarial.py
class TestAdversarial:
    """
    Teste la robustesse contre les attaques connues.
    """
    @pytest.mark.parametrize("attack", [
        "prompt_injection_ignore_previous",
        "prompt_injection_role_play",
        "prompt_injection_dan",
        "jailbreak_base64",
        "jailbreak_multi_lang",
        "prompt_leak_system",
    ])
    async def test_prompt_injection_resistance(self, attack: str):
        payload = self.load_adversarial_payload(attack)
        response = await self.pipeline.query(payload)
        assert response.guardrail_triggered, f"Failed to block: {attack}"
        assert "refus" in response.content.lower()

    async def test_token_budget_exhaustion(self):
        """L'attaquant ne doit pas pouvoir épuiser le budget token."""
        payload = "Repeat the entire text..." * 1000
        response = await self.pipeline.query(payload)
        assert response.truncated
        assert response.tokens_used <= self.config.max_tokens_per_query
```

## Tests de Charge

```python
# tests/load/test_load.py
"""
À exécuter avec locust :
  locust -f tests/load/test_load.py --host https://staging.example.com
"""
from locust import HttpUser, task, between

class GenAIUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def query_no_cache(self):
        self.client.post(
            "/api/v1/query",
            json={"query": "What is MLOps?", "use_cache": False},
        )

    @task(3)
    def query_with_cache(self):
        self.client.post(
            "/api/v1/query",
            json={"query": "What is RAG?", "use_cache": True},
        )

# Objectifs :
# - Latence P50 < 2s avec cache
# - Latence P95 < 5s sans cache
# - 0 erreur HTTP 5xx
# - Pas de dégradation sous charge soutenue (30 min)
```

## Tests Chaos

```python
# tests/chaos/test_chaos.py
@pytest.mark.chaos
class TestChaos:
    async def test_chaos_model_down(self):
        """Un model down ne doit pas casser l'app."""
        async with ChaosSimulator() as chaos:
            chaos.kill_service("openai-gateway")
            response = await self.pipeline.query("Hello")
            assert response.status == 200
            assert "claude" in response.model  # fallback actif

    async def test_chaos_redis_down(self):
        """Redis down → pas de cache, mais l'app fonctionne."""
        async with ChaosSimulator() as chaos:
            chaos.kill_service("redis")
            response = await self.pipeline.query("Hello")
            assert response.status == 200
            assert response.from_cache is False

    async def test_chaos_high_latency(self):
        """Simuler une latence réseau anormale."""
        async with ChaosSimulator() as chaos:
            chaos.add_latency("qdrant", delay_ms=2000)
            response = await self.pipeline.query("Hello")
            assert response.status == 200
            assert response.total_latency_ms < 10000  # timeout géré
```

## Couverture requise

| Type | Couverture cible | CI bloque si |
|---|---|---|
| Unit tests | > 90% | < 80% |
| Component tests | > 80% | < 70% |
| Regression prompts | 100% des scénarios | Échec ou drop > 5% |
| Adversarial | 100% des attaques connues | Échec |
| Load (P95) | < 5s | > 10s |
| Chaos | Tous les SPOF identifiés | Échec |

## Pièges à éviter
- ❌ Tester la couverture mais pas la qualité des réponses LLM
- ❌ Pas de regression prompts → changement de LLM = régression silencieuse
- ❌ Tests de charge sans simulation de latence LLM (trop optimistes)
- ❌ Ignorer les tests adversariaux → vulnérabilité
