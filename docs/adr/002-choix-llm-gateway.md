# ADR 002 — Choix du LLM Gateway

## Statut
Accepté

## Contexte
Nous avons besoin d'un proxy unifié pour gérer les appels aux différents fournisseurs LLM, avec rate limiting, fallback et observabilité.

## Options envisagées
- **LiteLLM** : open source, 100+ providers, proxy HTTP, fallback, rate limiting
- **Portkey** : SaaS, fonctionnalités avancées mais vendor lock-in
- **Custom** : développement interne, maintenance lourde
- **OpenRouter** : SaaS, bon mais pas self-hosted

## Décision
LiteLLM

## Raisons
- **100+ providers supportés** : OpenAI, Anthropic, Mistral, Groq, etc.
- **Proxy HTTP** : déploiement simple, compatible avec tout client OpenAI
- **Fallback + Circuit breaker** : natif
- **Rate limiting** : par modèle, par clé API, sliding window
- **Open source** : self-hosted, pas de dépendance externe
- **Budget tracking** : coût par clé API, alerte de dépassement

## Conséquences
- ✅ Déploiement simple via Docker, config YAML
- ✅ Observabilité via Prometheus metrics
- ❌ Configuration avancée nécessite des custom hooks (Python)
