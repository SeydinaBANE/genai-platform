# Couche 12 — Load Testing & Chaos Engineering

## Objectif
Valider la résilience de la plateforme sous charge et face aux défaillances avant qu'elles n'arrivent en production.

## Stack
- **Load Testing** : Locust (Python), vegeta (Go)
- **Chaos Engineering** : Chaos Mesh (K8s), custom Python simulator
- **Simulation** : latence LLM, défaillances réseau, crash de services
- **Observabilité** : metrics pendant le test, comparaison avant/après

## Load Testing — Locust

```python
# tests/load/locustfile.py
import random
from locust import HttpUser, task, between, events

test_queries = [
    "What is RAG?",
    "Explain vector embeddings",
    "How does MLOps work?",
    "What are guardrails in AI?",
    # ... 100+ queries
]

class GenAIUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        """Simule un vrai utilisateur avec un historique."""
        self.session_id = f"session-{random.randint(1, 10000)}"
        self.headers = {"X-Tenant-ID": f"tenant-{random.randint(1, 50)}"}

    @task(5)
    def query_with_cache(self):
        """Requêtes avec cache — doit être rapide."""
        query = random.choice(test_queries)
        with self.client.post(
            "/api/v1/query",
            json={"query": query, "use_cache": True},
            headers=self.headers,
            catch_response=True,
            name="query_cached",
        ) as resp:
            if resp.elapsed.total_seconds() > 2:
                resp.failure(f"Too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(2)
    def query_no_cache(self):
        """Requêtes sans cache — test de la pipeline complète."""
        query = random.choice(test_queries)
        with self.client.post(
            "/api/v1/query",
            json={"query": query, "use_cache": False},
            headers=self.headers,
            catch_response=True,
            name="query_uncached",
        ) as resp:
            if resp.elapsed.total_seconds() > 10:
                resp.failure(f"Too slow: {resp.elapsed.total_seconds():.2f}s")

    @task(1)
    def query_complex(self):
        """Requêtes complexes — beaucoup de contexte."""
        with self.client.post(
            "/api/v1/query",
            json={
                "query": "Compare and contrast all approaches",
                "use_cache": False,
                "max_contexts": 20,
            },
            headers=self.headers,
            catch_response=True,
            name="query_complex",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status: {resp.status_code}")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Starting load test...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"Test complete. Total requests: {environment.stats.total.num_requests}")
```

## Chaos Engineering — Scénarios

```python
# tests/chaos/scenarios.py
class ChaosScenarios:
    @pytest.mark.chaos
    async def test_model_provider_down(self):
        """Le provider OpenAI est injoignable."""
        async with self.chaos.block_host("api.openai.com"):
            response = await self.client.post("/api/v1/query", json={"query": "Hello"})
            assert response.status_code == 200
            assert "claude" in response.json()["model"]
            # Le fallback vers Claude a fonctionné

    @pytest.mark.chaos
    async def test_vector_store_slow(self):
        """Qdrant répond avec 2s de latence."""
        async with self.chaos.add_latency("qdrant:6333", delay_ms=2000):
            start = time.time()
            response = await self.client.post("/api/v1/query", json={"query": "Hello"})
            elapsed = time.time() - start
            assert response.status_code == 200
            assert elapsed < 15  # Timeout géré

    @pytest.mark.chaos
    async def test_redis_cache_down(self):
        """Redis est down — le cache est désactivé, pas de plantage."""
        async with self.chaos.kill_service("redis:6379"):
            response = await self.client.post(
                "/api/v1/query", json={"query": "Hello", "use_cache": True}
            )
            assert response.status_code == 200
            assert response.json()["from_cache"] is False

    @pytest.mark.chaos
    async def test_network_partition(self):
        """Perte de connectivité entre les services."""
        async with self.chaos.network_partition("app", "qdrant"):
            response = await self.client.post("/api/v1/query", json={"query": "Hello"})
            assert response.status_code == 503
            assert "Service Unavailable" in response.text

    @pytest.mark.chaos
    async def test_memory_pressure(self):
        """Pression mémoire sur le service."""
        async with self.chaos.memory_pressure(target="app", percentage=80):
            response = await self.client.post("/api/v1/query", json={"query": "Hello"})
            assert response.status_code in (200, 503)  # OK ou dégradé propre

    @pytest.mark.chaos
    async def test_all_providers_down(self):
        """Tous les providers LLM sont down."""
        async with self.chaos.block_hosts(["api.openai.com", "api.anthropic.com", "api.mistral.ai"]):
            response = await self.client.post("/api/v1/query", json={"query": "Hello"})
            assert response.status_code == 503
            assert all_providers_down
```

## Runbook Chaos

```makefile
chaos-run: ## Exécute les tests chaos
	pytest tests/chaos/ -v --chaos -x --timeout=120

chaos-run-all: ## Exécute tous les scénarios chaos
	pytest tests/chaos/ -v --chaos --timeout=300

chaos-k8s: ## Injecte du chaos dans le cluster K8s
	kubectl apply -f tests/chaos/k8s/network-delay.yaml
	kubectl apply -f tests/chaos/k8s/pod-kill.yaml

chaos-clean: ## Nettoie les expériences chaos K8s
	kubectl delete chaosexperiment --all -n genai-platform

load-test: ## Exécute les tests de charge
	locust -f tests/load/locustfile.py \
	  --host https://staging.example.com \
	  --users 50 \
	  --spawn-rate 5 \
	  --run-time 30m \
	  --headless \
	  --csv results/load-test

load-test-report: ## Génère le rapport de test de charge
	@echo "=== Load Test Results ==="
	@python -c "
	import pandas as pd
	df = pd.read_csv('results/load-test_stats.csv')
	print(f'Total requests: {df[\"Request Count\"].sum()}')
	print(f'Failure rate: {df[\"Failure Count\"].sum() / df[\"Request Count\"].sum():.2%}')
	print(f'Average response time: {df[\"Average Response Time\"].mean():.0f}ms')
	print(f'P95 response time: {df[\"95% Response Time\"].mean():.0f}ms')
	"
```

## Objectifs de Résilience

| Scénario | Comportement attendu | SLA |
|---|---|---|
| 1 provider LLM down | Fallback transparent | < 1s de latence supplémentaire |
| Tous les providers down | 503 gracieux + message explicatif | < 5s de détection |
| Redis down | Cache désactivé, requêtes pass-through | < 500ms d'impact |
| Qdrant lent | Timeout + réponse "aucun document trouvé" | < 15s |
| Pod crash | Redémarrage K8s (< 30s) | < 2% d'erreurs |
| Pic de trafic (10x) | Rate limiting, pas de crash | 0% d'erreurs 5xx |
| Network partition | Isolation propre d'un service | Pas de corruption de données |

## Pièges à éviter
- ❌ Tests de charge en local (pas représentatif)
- ❌ Chaos non isolé → risque de contamination de la prod
- ❌ Pas de cleanup après test chaos → services still down
- ❌ Load test sans monitoring → tu sais pas ce qui casse
- ❌ Un seul scénario de load → rate la diversité des comportements
