# Couche 8 — Feedback & Évaluation Continue

## Objectif
Collecter le feedback utilisateur, évaluer la qualité des réponses et améliorer continuellement la plateforme.

## Stack
- **Feedback** : thumbs up/down, rating 1-5, correction libre
- **Human-in-the-loop** : validation humaine des cas litigieux
- **Évaluation** : RAGAS, DeepEval, LLM-as-Judge
- **Stockage** : PostgreSQL (feedback) + LangFuse (traces + scores)

## Architecture

```
[Réponse LLM]
      ↓
[Widget Feedback] → [API Feedback] → [PostgreSQL]
      ↓                                    ↓
[Thumbs / Rating / Correction]      [LangFuse Score]
      ↓                                    ↓
[Analyse Hebdomadaire] ← [Aggregation] ← [Quality Dashboard]
      ↓
[Amélioration]
  ├── A/B test nouveau prompt
  ├── Fine-tuning embedding model
  ├── Ajout de sources documentaires
  └── Ajustement chunking
```

## Collecte Feedback

```python
class FeedbackService:
    async def submit_feedback(
        self,
        trace_id: str,
        tenant: str,
        rating: int,
        comment: str | None = None,
        correction: str | None = None,
    ):
        # Stocker dans PostgreSQL
        await self.db.execute(
            "INSERT INTO feedback (trace_id, tenant, rating, comment, correction) "
            "VALUES ($1, $2, $3, $4, $5)",
            trace_id, tenant, rating, comment, correction,
        )

        # Envoyer le score à LangFuse
        self.langfuse.score(
            trace_id=trace_id,
            name="user_rating",
            value=rating / 5.0,  # normalisé 0-1
            comment=comment,
        )

        # Si correction fournie, la stocker comme ground truth
        if correction:
            await self._store_ground_truth(trace_id, correction)
```

## LLM-as-Judge

```python
class LLMJudge:
    async def evaluate_response(
        self,
        query: str,
        response: str,
        contexts: list[str],
    ) -> dict:
        prompt = f"""
        You are an expert evaluator. Assess the quality of the response.

        Query: {query}
        Response: {response}
        Contexts: {' '.join(contexts)}

        Rate each criterion 0.0-1.0:
        - helpfulness: does it answer the query?
        - truthfulness: is it supported by the context?
        - completeness: does it cover all aspects?
        - conciseness: is it free of verbosity?
        - safety: is it free of harmful content?

        Return a JSON object with scores and reasoning.
        """

        result = await self.llm.complete(prompt, model="gpt-4o", response_format="json")

        return {
            "helpfulness": result["helpfulness"],
            "truthfulness": result["truthfulness"],
            "completeness": result["completeness"],
            "conciseness": result["conciseness"],
            "safety": result["safety"],
            "composite": sum(result.values()) / len(result),
            "reasoning": result.get("reasoning", ""),
        }
```

## Human-in-the-Loop

```python
class HumanInTheLoop:
    FLAGGED_THRESHOLD = 0.6

    async def process_response(self, query: str, response: str) -> str:
        quality = await self.llm_judge.evaluate_response(query, response, [])

        if quality["composite"] < self.FLAGGED_THRESHOLD:
            # Envoyer pour validation humaine
            task_id = await self._create_review_task(query, response, quality)
            return await self._wait_for_human_review(task_id, timeout=300)
        else:
            return response

    async def escalation_queue(self) -> list[dict]:
        return await self.db.fetch(
            "SELECT * FROM review_tasks WHERE status = 'pending' ORDER BY priority DESC"
        )
```

## Métriques de Qualité

```python
class QualityMetrics:
    async def compute_weekly(self, tenant: str) -> dict:
        feedback = await self.db.fetch("""
            SELECT
                AVG(rating) as avg_rating,
                COUNT(*) as total_feedback,
                SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative_count,
                COUNT(DISTINCT trace_id) as total_queries
            FROM feedback
            WHERE tenant = $1
              AND created_at > NOW() - INTERVAL '7 days'
        """, tenant)

        return {
            "avg_rating": feedback["avg_rating"] / 5.0,
            "csat": feedback["avg_rating"] / 5.0 * 100,
            "negative_rate": feedback["negative_count"] / feedback["total_feedback"],
            "feedback_coverage": feedback["total_feedback"] / feedback["total_queries"],
            "trend": await self._compute_trend(tenant),
        }
```

## Production thresholds

| Métrique | Cible | Alerte |
|---|---|---|
| CSAT moyen | > 85% | < 75% |
| Feedback coverage | > 10% | < 5% |
| Negative rate | < 5% | > 10% |
| Human review TTV | < 5 min | > 30 min |
| LLM Judge agreement | > 80% | < 70% |

## Pièges à éviter
- ❌ Pas de feedback → tu pilotes sans instruments
- ❌ LLM Judge non calibré (le juge peut être plus mauvais que le modèle jugé)
- ❌ Feedback trop lourd → personne ne l'utilise (1 clic max)
- ❌ Corrections non utilisées → perte de gold data
