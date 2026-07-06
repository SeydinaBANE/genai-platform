# Couche 1 — Infrastructure

## Objectif
Fournir une infrastructure scalable, sécurisée et reproductible pour l'ensemble de la plateforme GenAI.

## Stack
- **Container** : Docker multi-stage, images distroless
- **Orchestrateur** : Kubernetes (EKS / GKE)
- **GitOps** : ArgoCD
- **Secrets** : HashiCorp Vault / SOPS + age
- **Ingress** : Traefik / nginx-ingress
- **Certificats** : cert-manager + Let's Encrypt

## Bonnes pratiques senior — Docker

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
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
EXPOSE 8000
ENTRYPOINT ["python", "-m", "uvicorn", "genai_platform.adapters.http.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Règles :
- **Toujours multi-stage** : builder + runtime, jamais de dépendances de build en prod
- **Image distroless** : pas de shell, pas de package manager, surface d'attaque minimale
- **Utilisateur non-root** : `USER nonroot` — jamais root dans le conteneur
- **Pin les versions** : `FROM python:3.11-slim` pas `:latest`
- **Healthcheck** : obligatoire pour K8s liveness/readiness
- **COPY --chown** : permissions explicites
- **Pas de secrets dans l'image** : --secret=id=... via BuildKit

## Bonnes pratiques senior — Makefile

```makefile
.PHONY: docker-build docker-scan docker-tag

docker-build:
    docker build \
      --secret id=netrc,src=$(HOME)/.netrc \
      --cache-from type=gha \
      --cache-to type=gha,mode=max \
      -t genai-platform:$(GIT_SHA) .

docker-scan:
    trivy image --severity HIGH,CRITICAL --exit-code 1 genai-platform:$(GIT_SHA)

docker-tag:
    docker tag genai-platform:$(GIT_SHA) ghcr.io/ekkiden/genai-platform:$(GIT_SHA)
```

## Bonnes pratiques senior — pre-commit

```yaml
- repo: local
  hooks:
    - id: dockerfile-lint
      name: Dockerfile lint
      entry: hadolint Dockerfile
      language: system
      files: ^Dockerfile$
```

## Bonnes pratiques senior — GitHub

- **Branch protection** : `main` protégée, PR obligatoire, status checks requis
- **Review rules** : min 2 approvals pour `main`
- **CODEOWNERS** : chaque couche a un propriétaire
- **Git tagging** : tags signés, `v*` pour releases

## Sécurité
- Secrets jamais dans Git → Vault ou SOPS
- Image signing (cosign) + SBOM (syft)
- Network policies K8s : isolation par namespace
- Pod Security Standards : restricted profile

## Runbook
```bash
make docker-build        # Build l'image
make docker-scan         # Scan de vulnérabilités
make docker-up           # Stack locale complète
kubectl get pods -n genai-platform
argocd app sync genai-platform
```

## Pièges à éviter
- ❌ Utiliser `:latest` en production
- ❌ Root user dans le conteneur
- ❌ Multi-stage sans `--from` explicite
- ❌ Ignorer les scans de vulnérabilités
- ❌ Hardcoder des secrets dans docker-compose.yml
