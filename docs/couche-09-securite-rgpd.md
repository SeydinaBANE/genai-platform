# Couche 9 — Sécurité & RGPD

## Objectif
Assurer la conformité RGPD, la sécurité des données et la résilience de la plateforme.

## Principes fondamentaux
- **Privacy by Design** : les données personnelles sont exclues du processing LLM par défaut
- **Data Minimization** : on ne collecte que ce qui est nécessaire
- **Right to Erasure** : possibilité de supprimer toutes les données d'un utilisateur
- **Audit Trail** : chaque accès est loggé et horodaté

## PII Handling

```
[User Input]
      ↓
[Presidio Analyzer] → PII détecté ?
      |                          |
    Oui                         Non
      |                          |
[Anonymisation]             [Pass Through]
      |                          |
[Remplacé par [REDACTED]]    [Texte original]
      |
[LLM (aucune donnée PII)]
      |
[Post-processing] → Vérifier que le LLM n'a pas "halluciné" de la PII
      |
[Response]
```

## Encryption

```python
class EncryptionManager:
    def __init__(self):
        # AES-256-GCM pour les données au repos
        self.cipher = Fernet(os.environ["ENCRYPTION_KEY"].encode())

    def encrypt_trace(self, trace_data: dict) -> dict:
        encrypted = {}
        for key in trace_data:
            if key in self.sensitive_fields:
                encrypted[key] = self.cipher.encrypt(
                    json.dumps(trace_data[key]).encode()
                ).decode()
            else:
                encrypted[key] = trace_data[key]
        return encrypted

    async def right_to_erasure(self, user_id: str) -> None:
        async with self.db.transaction():
            await self.db.execute("DELETE FROM feedback WHERE tenant = $1", user_id)
            await self.db.execute("DELETE FROM traces WHERE tenant = $1", user_id)
            await self.db.execute("DELETE FROM sessions WHERE tenant = $1", user_id)
            await self.qdrant.delete(
                collection_name="documents",
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="tenant", MatchValue(value=user_id))]
                    )
                ),
            )
            await self.audit_log("right_to_erasure", {"user_id": user_id})
```

## RGPD Checklist

- [ ] Consentement explicite avant traitement
- [ ] DPO nommé et contactable
- [ ] Registre des traitements à jour
- [ ] Analyse d'impact (AIPD) réalisée
- [ ] Clauses contractuelles avec les sous-traitants (OpenAI, Anthropic, etc.)
- [ ] Données hébergées en UE (ou adequacy decision)
- [ ] Encryption AES-256 pour les données au repos
- [ ] TLS 1.3 pour les données en transit
- [ ] Logs d'accès conservés 6 mois max
- [ ] Procédure de right to erasure automatisée
- [ ] Data retention policy documentée

## Audit Trail

```python
class AuditService:
    async def log(
        self,
        action: str,
        actor: str,
        resource: str,
        details: dict | None = None,
    ):
        await self.db.execute(
            """
            INSERT INTO audit_log (action, actor, resource, details, ip_address, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            action,
            actor,
            resource,
            json.dumps(details) if details else None,
            self.request.client.host,
        )

    async def query(self, filters: AuditFilter) -> list[dict]:
        return await self.db.fetch(
            """
            SELECT * FROM audit_log
            WHERE ($1::text IS NULL OR action = $1)
              AND ($2::text IS NULL OR actor = $2)
              AND created_at BETWEEN $3 AND $4
            ORDER BY created_at DESC
            LIMIT $5
            """,
            filters.action,
            filters.actor,
            filters.date_from,
            filters.date_to,
            filters.limit or 100,
        )
```

## Vulnerability Management

```makefile
security-scan: ## Scan complet de sécurité
	trivy image --severity CRITICAL genai-platform:latest
	trivy fs --severity HIGH,CRITICAL .
	pip-audit

security-sbom: ## Générer le SBOM
	syft genai-platform:latest -o spdx-json > sbom.spdx.json

security-sign: ## Signer l'image
	cosign sign --key cosign.key ghcr.io/ekkiden/genai-platform:$(GIT_SHA)

security-verify: ## Vérifier la signature
	cosign verify --key cosign.pub ghcr.io/ekkiden/genai-platform:$(GIT_SHA)
```

## Data Retention

| Type de donnée | Rétention | Suppression |
|---|---|---|
| Logs d'accès | 6 mois | Automatique (cron) |
| Feedback | 12 mois | Sur demande |
| Traces LangFuse | 3 mois | Automatique (TTL) |
| Données vectorielles | Durée du contrat | Right to erasure |
| Ground truth | 24 mois | Anonymisée après 12 mois |

## Pièges à éviter
- ❌ Stocker des logs sans purge automatique
- ❌ Envoyer des données PII à OpenAI/Anthropic sans anonymisation
- ❌ Pas de right to erasure → amende CNIL jusqu'à 4% du CA
- ❌ Clés API dans le code → fuite de secrets
- ❌ Pas d'audit trail → impossible de tracer une fuite
