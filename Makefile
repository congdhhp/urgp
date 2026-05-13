.PHONY: help up down logs shell migrate migrate-down migrate-reset seed install test test-backend test-cli test-frontend test-integration test-e2e test-perf test-all lint format type-check check build-images clean

COMPOSE := docker compose -f deploy/docker-compose.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

shell: ## Open shell in urgp-api container
	$(COMPOSE) exec urgp-api bash

migrate: ## Run database migrations
	$(COMPOSE) exec urgp-api alembic upgrade head

migrate-down: ## Roll back last migration
	$(COMPOSE) exec urgp-api alembic downgrade -1

migrate-reset: ## Reset database migrations
	$(COMPOSE) exec urgp-api alembic downgrade base
	$(COMPOSE) exec urgp-api alembic upgrade head

seed: ## Seed sample data
	$(COMPOSE) exec urgp-api python -m urgp.db.seed

install: ## Install backend, CLI, and frontend dependencies
	cd backend && poetry install
	cd cli && poetry install
	cd frontend/portal && npm ci

test: test-backend test-cli test-frontend ## Run backend, CLI, and frontend tests

test-backend: ## Run backend unit tests
	cd backend && poetry run pytest tests/unit/ -v --cov=src/urgp --cov-report=term-missing

test-cli: ## Run CLI unit tests
	cd cli && poetry run pytest tests/ -v --cov=src/urgp_cli --cov-report=term-missing

test-frontend: ## Run frontend tests
	cd frontend/portal && npm run test

test-integration: ## Run backend integration tests
	cd backend && poetry run pytest tests/integration/ -v -m integration

test-e2e: ## Run backend E2E pipeline tests
	cd backend && poetry run pytest tests/integration/test_e2e_pipeline.py tests/integration/test_data_accuracy.py -v -m integration --timeout=60

test-perf: ## Run backend performance tests
	cd backend && poetry run pytest tests/integration/test_performance.py -v -m slow --timeout=120 -s

test-all: ## Run all backend and CLI tests
	cd backend && poetry run pytest tests/ -v --timeout=60
	cd cli && poetry run pytest tests/ -v

lint: ## Run backend and CLI linters
	cd backend && poetry run ruff check .
	cd cli && poetry run ruff check .

format: ## Format backend and CLI code
	cd backend && poetry run ruff format .
	cd cli && poetry run ruff format .

type-check: ## Run backend and CLI type checks
	cd backend && poetry run mypy src/
	cd cli && poetry run mypy src/

check: lint type-check test-backend test-cli ## Run main quality checks

build-images: ## Build backend and portal Docker images
	docker build -f deploy/Dockerfile.backend -t urgp-api:local .
	docker build -f deploy/Dockerfile.portal -t urgp-portal:local .

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/htmlcov backend/.coverage cli/htmlcov cli/.coverage frontend/portal/dist

.DEFAULT_GOAL := help
