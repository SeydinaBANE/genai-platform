# Couche 7 — Industrialisation & CI/CD

## Objectif
Automatiser le build, test, déploiement et rollback de la plateforme avec zéro temps d'arrêt.

## Stack
- **CI** : GitHub Actions (matrix build, caching)
- **CD** : ArgoCD (GitOps) + blue/green
- **Feature Flags** : LaunchDarkly / Flagsmith
- **Container Registry** : GHCR (scan + signing)
- **Environments** : dev → staging → production (promotion)

## Pipeline CI

```yaml
# .github/workflows/ci.yml — déjà créé, cf. fichier
# Points clés additionnels :

jobs:
  eval-regression:
    name: Prompt Regression Tests
    runs-on: ubuntu-latest
    steps:
      - name: Run eval suite
        run: |
          python -m pytest tests/eval/ -v --eval-dataset datasets/regression.jsonl
          python -m scripts.compare_eval --baseline baseline.json --current results.json

      - name: Fail if regression
        run: |
          python -c "
          import json
          with open('comparison.json') as f:
              data = json.load(f)
          if data['faithfulness_drop'] > 0.05:
              print(f'Faithfulness regressed by {data[\"faithfulness_drop\"]:.2%}')
              exit(1)
          "
```

## Blue/Green Deploy

```python
# scripts/blue_green.py
class BlueGreenDeploy:
    def deploy(self, image: str, namespace: str, service: str):
        active = self._get_active_deployment(service)
        inactive = "green" if active == "blue" else "blue"

        # 1. Deployer sur l'environnement inactif
        self._deploy(inactive, image, namespace)

        # 2. Attendre que le healthcheck passe
        self._wait_for_healthy(inactive, namespace)

        # 3. Basculer le trafic
        self._switch_traffic(service, inactive, namespace)

        # 4. Garder l'ancien pour rollback immédiat
        print(f"Deploy successful. Active: {inactive}, Standby: {active}")
```

## Feature Flags

```python
class FeatureFlags:
    def __init__(self, provider: str = "flagsmith"):
        self.client = FlagsmithClient(
            environment_key=os.environ["FLAGSMITH_KEY"],
        )

    async def is_enabled(self, feature: str, tenant: str) -> bool:
        identity = self.client.get_identity(tenant)
        return identity.get_feature_state(feature).enabled

    # Utilisation :
    # if await flags.is_enabled("new-reranker", tenant):
    #     return await new_reranker.rank(query, docs)
    # else:
    #     return await old_reranker.rank(query, docs)
```

## Auto-rollback

```python
class AutoRollback:
    def __init__(self, prometheus_url: str):
        self.prom = PrometheusConnect(url=prometheus_url)

    async def monitor_deploy(self, deploy_id: str, timeout: int = 300):
        start = time.time()
        while time.time() - start < timeout:
            metrics = await self._get_post_deploy_metrics()

            if metrics["error_rate"] > 0.05:
                await self._rollback(deploy_id, reason="Error rate > 5%")
                return False
            if metrics["p99_latency"] > 10:
                await self._rollback(deploy_id, reason="P99 latency > 10s")
                return False
            if metrics["quality_score"] < 0.7:
                await self._rollback(deploy_id, reason="Quality score < 0.7")
                return False

            await asyncio.sleep(10)

        return True
```

## Makefile targets

```makefile
deploy-staging: ## Déploie en staging via CI
	gh workflow run deploy.yml -f environment=staging -f version=$(GIT_SHA)

deploy-production: ## Déploie en production (depuis staging)
	gh workflow run deploy.yml -f environment=production -f version=$(STAGING_TAG)

rollback: ## Rollback au tag précédent
	gh workflow run deploy.yml -f environment=production -f version=$(PREVIOUS_TAG)

promote: ## Propage staging → production
	@echo "Promoting $(STAGING_TAG) to production..."
	gh workflow run deploy.yml -f environment=production -f version=$(STAGING_TAG)

smoke-test: ## Test post-deploy
	@echo "Running smoke tests..."
	curl -sf https://staging.example.com/health
	curl -sf https://staging.example.com/api/v1/ready
```

## Environnements

| Environnement | Déclencheur | Auto-déploy | Auto-rollback | Données |
|---|---|---|---|---|
| **dev** | push devlop | ✅ | ❌ | Synthétiques |
| **staging** | PR merged → main | ✅ | ✅ | Anonymisées |
| **production** | manual promote | ❌ (manual) | ✅ (automatique) | Réelles |

## Pièges à éviter
- ❌ Déploiement direct en production sans staging
- ❌ Pas d'auto-rollback → incident long
- ❌ CI sans cache Docker → builds lents (x5)
- ❌ Tests de regression prompts manquants → régression silencieuse
- ❌ Feature flags sans cleanup → dette technique
