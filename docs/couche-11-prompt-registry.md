# Couche 11 — Prompt Registry

## Objectif
Gérer les prompts de manière centralisée : versioning, A/B testing, rollback, tracking de performance.

## Architecture

```
[Prompt Registry DB]
        ↓
[Git (YAML source of truth)]
        ↓
[CI/CD] → Validation → Sync to DB
        ↓
[API Registry] ← [Application]
        ↓
[LangFuse Tracking] → [Performance Dashboard]
```

## Structure du Registry

```yaml
# prompts/qa-system-v1.yaml
version: 1
name: qa-system
description: "Prompt système pour le RAG Q&A"
model: gpt-4o
temperature: 0.1
max_tokens: 2048
system_prompt: |
  Tu es un assistant expert spécialisé dans la réponse aux questions
  basées sur les documents fournis.

  Règles :
  1. Réponds UNIQUEMENT en te basant sur le contexte fourni.
  2. Si la réponse ne se trouve pas dans le contexte, dis "Je ne trouve pas cette information dans les documents fournis."
  3. Cite tes sources avec le numéro de document : [1], [2], etc.
  4. Utilise un langage clair et professionnel.

  Contexte :
  {context}

  Question : {query}
eval_threshold:
  faithfulness: 0.85
  relevancy: 0.80
```

## Registry Manager

```python
class PromptRegistry:
    def __init__(self, db, redis):
        self.db = db
        self.cache = redis

    async def get_active(self, prompt_name: str, tenant: str) -> Prompt:
        cache_key = f"prompt:{prompt_name}:{tenant}"

        # 1. Vérifier le cache
        cached = await self.cache.get(cache_key)
        if cached:
            return Prompt.model_validate_json(cached)

        # 2. Vérifier un A/B test actif pour ce tenant
        ab_test = await self._get_active_ab_test(prompt_name, tenant)
        if ab_test:
            variant = await self._assign_variant(tenant, ab_test)
            prompt = await self._get_prompt_version(ab_test.variants[variant])
        else:
            # 3. Prompt par défaut
            prompt = await self._get_prompt_version(
                await self._get_default_version(prompt_name)
            )

        await self.cache.setex(cache_key, 300, prompt.model_dump_json())
        return prompt

    async def get_version(self, prompt_name: str, version: int) -> Prompt:
        return await self._get_prompt_version(version)

    async def rollback(self, prompt_name: str, version: int) -> Prompt:
        """Rollback vers une version précédente."""
        prompt = await self._get_prompt_version(version)
        await self._set_default_version(prompt_name, version)
        await self._log_rollback(prompt_name, version)
        return prompt
```

## A/B Testing

```python
class ABTesting:
    async def create_test(
        self,
        prompt_name: str,
        variants: dict[str, int],  # {variant_name: version_id}
        traffic_split: dict[str, float],  # {variant_name: 0.5}
        duration_hours: int = 48,
    ):
        test = ABTest(
            prompt_name=prompt_name,
            variants=variants,
            traffic_split=traffic_split,
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow() + timedelta(hours=duration_hours),
        )
        return await self.db.insert("ab_tests", test)

    async def analyze(self, test_id: str) -> dict:
        results = await self.db.fetch("""
            SELECT
                variant,
                AVG(rating) as avg_rating,
                COUNT(*) as total,
                AVG(latency_ms) as avg_latency,
                AVG(cost) as avg_cost
            FROM ab_test_results
            WHERE test_id = $1
            GROUP BY variant
        """, test_id)

        winner = max(results, key=lambda r: r["avg_rating"])
        return {
            "winner": winner["variant"],
            "improvement": winner["avg_rating"] - min(r["avg_rating"] for r in results),
            "is_significant": self._statistical_significance(results),
            "details": results,
        }
```

## Performance Tracking

```python
class PromptPerformance:
    async def get_dashboard(self, prompt_name: str) -> dict:
        return await self.db.fetch("""
            SELECT
                version,
                COUNT(*) as total_queries,
                AVG(rating) as avg_rating,
                AVG(faithfulness) as avg_faithfulness,
                AVG(latency_ms) as avg_latency,
                AVG(cost_per_query) as avg_cost,
                SUM(CASE WHEN guardrail_triggered THEN 1 ELSE 0 END) as guardrail_count
            FROM prompt_metrics
            WHERE prompt_name = $1
              AND created_at > NOW() - INTERVAL '30 days'
            GROUP BY version
            ORDER BY version DESC
        """, prompt_name)
```

## CI for Prompts

```yaml
# CI step for prompt changes
jobs:
  validate-prompts:
    runs-on: ubuntu-latest
    steps:
      - name: Validate prompt YAML
        run: python -c "
          import yaml, glob
          for f in glob.glob('prompts/*.yaml'):
              with open(f) as fp:
                  data = yaml.safe_load(fp)
              assert 'name' in data
              assert 'version' in data
              assert 'system_prompt' in data
          "

      - name: Validate variables
        run: python -c "
          import re, yaml, glob
          for f in glob.glob('prompts/*.yaml'):
              with open(f) as fp:
                  data = yaml.safe_load(fp)
              required = re.findall(r'\{(\w+)\}', data['system_prompt'])
              print(f'{f}: variables {required}')
          "

      - name: Dry-run eval on new prompt
        run: |
          python -m scripts.eval_prompt \
            --prompt prompts/qa-system-v2.yaml \
            --dataset datasets/regression.jsonl \
            --output results/new-prompt-eval.json

      - name: Compare with baseline
        run: |
          python -m scripts.compare_eval \
            --baseline results/baseline.json \
            --current results/new-prompt-eval.json
```

## Workflow Git pour les Prompts

```bash
# Les prompts sont versionnés dans Git ET en DB
# Git = source of truth, DB = runtime

# 1. Créer une nouvelle version
cp prompts/qa-system-v1.yaml prompts/qa-system-v2.yaml
# modifier le fichier...

# 2. Commit + PR
git add prompts/qa-system-v2.yaml
git commit -m "prompt(qa): v2 — better source citation"
# PR → review → merge

# 3. CI: validation + eval → sync auto en DB
# Le registry est automatiquement mis à jour
```

## Pièges à éviter
- ❌ Prompts en dur dans le code → modification = déploiement
- ❌ Pas de version → impossible de rollback
- ❌ A/B tests trop courts (< 24h) → pas statistiquement significatifs
- ❌ Pas de validation → prompt malformé en prod
