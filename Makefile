.PHONY: help init lint typecheck test build docker-build docker-up \
        docker-down clean install-dev install-prod precommit precommit-all \
        security audit format

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Initialise l'environnement complet
	python3 -m venv .venv && \
	. .venv/bin/activate && \
	pip install --upgrade pip setuptools wheel && \
	pip install -e ".[dev,test,eval]" && \
	pre-commit install --hook-type pre-commit --hook-type pre-push && \
	pre-commit run --all-files

install-dev: ## Installe les dépendances de développement
	pip install -e ".[dev,test,eval]"

install-prod: ## Installe les dépendances de production uniquement
	pip install -e "."

lint: ## Vérifie le code avec ruff
	ruff check src/ tests/

lint-fix: ## Corrige automatiquement les erreurs ruff
	ruff check --fix src/ tests/

format: ## Formate le code avec ruff
	ruff format src/ tests/

typecheck: ## Vérifie les types avec mypy
	mypy src/

test: ## Exécute les tests unitaires
	python3 -m pytest tests/ -v --cov=src --cov-report=term-missing

test-coverage: ## Exécute les tests avec rapport de couverture HTML
	python3 -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term

test-watch: ## Exécute les tests en mode watch
	.find tests/ src/ | entr -c python3 -m pytest tests/ -v

test-integration: ## Exécute les tests d'intégration
	python3 -m pytest tests/ -v -m integration

precommit: ## Exécute pre-commit sur les fichiers modifiés
	pre-commit run

precommit-all: ## Exécute pre-commit sur tous les fichiers
	pre-commit run --all-files

security: ## Vérifie les secrets et vulnérabilités
	detect-secrets scan --baseline .secrets.baseline
	pip-audit

docker-build: ## Construit l'image Docker
	docker build -t genai-platform:latest .

docker-run: ## Lance le conteneur localement
	docker run --rm -p 8000:8000 genai-platform:latest

docker-up: ## Démarre la stack locale complète
	docker compose up -d

docker-down: ## Arrête la stack locale
	docker compose down -v

docker-logs: ## Affiche les logs Docker
	docker compose logs -f

docker-clean: ## Nettoie les images et volumes Docker
	docker compose down -v && docker system prune -f

build: lint typecheck test ## Exécute toutes les vérifications avant build

clean: ## Nettoie les artefacts locaux
	rm -rf .venv/ .mypy_cache/ .ruff_cache/ .pytest_cache/ \
	       __pycache__/ */__pycache__/ */*/__pycache__/ \
	       htmlcov/ .coverage *.egg-info/ dist/ build/

all: init build ## Initialise et vérifie tout le projet
