# Senior Best Practices — Synthèse Transversale

## Docker

- **Multi-stage build** : builder + runtime, jamais de dépendances de build en production
- **Image distroless** : pas de shell, pas de package manager, surface d'attaque minimale
- **Utilisateur non-root** : `USER nonroot` — jamais root dans le conteneur
- **Pin les versions** : `FROM python:3.11-slim` pas `:latest`
- **Healthcheck** : obligatoire pour K8s, test HTTP ou TCP
- **COPY --chown** : permissions explicites
- **`--secret` BuildKit** : pas de secrets dans les layers Docker
- **`.dockerignore`** : exclure .git, .venv, __pycache__, .env
- **~200MB max** : si ton image dépasse 500MB, tu as un problème
- **Trivy scan** : avant chaque push, bloquer les CRITICAL

```dockerfile
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-dev --frozen

FROM gcr.io/distroless/python3-debian12 AS runtime
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY src/ src/
USER nonroot
HEALTHCHECK CMD ["python", "-c", "urllib.request.urlopen('http://localhost:8000/health')"]
EXPOSE 8000
ENTRYPOINT ["python", "-m", "uvicorn", "genai_platform.api:app", "--host", "0.0.0.0"]
```

## Makefile

- **`.PHONY`** : pour toutes les cibles qui ne sont pas des fichiers
- **`make help`** : auto-documenté avec `##` comments
- **Idempotence** : `make init` peut être relancé sans danger
- **Composition** : `make build` = `lint + typecheck + test`
- **Variables au début** : `PYTHON := python3`, `DOCKER := docker`
- **Fail fast** : `set -e` dans les commandes multi-lignes
- **Respecter les standards** : `test`, `build`, `clean`, `install`, `lint`

```makefile
.PHONY: help lint build test
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

## pre-commit

- **Tous les types de fichiers** : YAML, JSON, TOML, Python, Shell, Markdown
- **detect-secrets** : baseline commitée, scan à chaque commit
- **Ruff** : lint + format, même config que CI
- **Mypy strict** : `--strict` pour le code applicatif, relaxé pour les tests
- **Performance** : hooks rapides (< 1s), hooks loux en CI uniquement

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.10
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: local
    hooks:
      - id: makefile-lint
        name: Makefile syntax check
        entry: sh -c "make -n 2>/dev/null || exit 0"
        language: system
        files: ^Makefile$
```

## GitHub

### Branch Protection Rules (main)
- ✅ Require pull request before merging
- ✅ Require approvals (2 minimum)
- ✅ Dismiss stale reviews
- ✅ Require status checks (lint, test, security)
- ✅ Require branches up to date
- ✅ Do not allow bypassing

### GitHub Actions

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

- **Matrix builds** : Python 3.11 + 3.12
- **Cache** : `actions/cache` pour pip, `docker/build-push-action` avec cache GHA
- **Secrets** : jamais en clair, utiliser GitHub Secrets
- **Minimal permissions** : `permissions: contents: read`
- **Dependabot** : auto-merge pour les patchs, review pour les minors/majors

### CODEOWNERS
- Chaque couche a un propriétaire explicite
- Les ADR appartiennent à tech-lead
- Les workflows CI/CD appartiennent à platform-eng

## Sécurité Générale

- **Secrets** : jamais dans le code. Vault/SOPS + `detect-secrets` en pre-commit
- **SBOM** : généré à chaque build (syft)
- **Image signing** : cosign, vérifié au déploiement
- **Règles** : least privilege, defense in depth, fail securely
- **Logs** : ne jamais logger de PII, de tokens, de mots de passe
- **Dépendances** : `pip-audit` en CI, dependabot, revue manuelle des breaking changes

## Qualité

| Vérification | Local (pre-commit) | CI (PR) | Bloque le merge |
|---|---|---|---|
| Ruff lint | ✅ | ✅ | ✅ |
| Ruff format | ✅ | ✅ | ✅ |
| Mypy strict | ✅ | ✅ | ✅ |
| Tests unitaires | ❌ | ✅ | ✅ |
| Tests intégration | ❌ | ✅ | ✅ |
| Tests eval régression | ❌ | ✅ | ✅ |
| Scan sécurité | ❌ | ✅ | ✅ |
| Scan Docker | ❌ | ✅ | ⚠️ (CRITICAL only) |
| Tests charge | ❌ | ❌ (manuel) | ❌ |
| Tests chaos | ❌ | ❌ (manuel) | ❌ |

## Prod-readiness Checklist

Avant chaque mise en production :

- [ ] `make build` passe (lint + typecheck + test)
- [ ] `make precommit-all` passe
- [ ] Image Docker scannée (0 CRITICAL)
- [ ] SBOM généré et stocké
- [ ] Image signée (cosign)
- [ ] Migration DB testée (forward + rollback)
- [ ] Changement backward compatible
- [ ] Monitoring mis à jour (alertes, dashboards)
- [ ] Runbook mis à jour
- [ ] Changelog mis à jour
- [ ] Tests de regression prompts passés
- [ ] Pas de secrets dans le diff
- [ ] PR approuvée par 2 reviewers
- [ ] Déploiement staging réussi + smoke tests
