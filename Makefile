.PHONY: up down logs shell test migrate lint format type-check clean seed help

# ─────────────────────────────────────────────
# Docker Compose
# ─────────────────────────────────────────────
up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

shell: ## Open shell in urgp-api container
	docker compose exec urgp-api bash

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
migrate: ## Run database migrations (upgrade to head)
	docker compose exec urgp-api alembic upgrade head

migrate-down: ## Rollback last migration
	docker compose exec urgp-api alembic downgrade -1

migrate-reset: ## Reset database (downgrade to base, then upgrade)
	docker compose exec urgp-api alembic downgrade base
	docker compose exec urgp-api alembic upgrade head

seed: ## Seed database with sample data
	docker compose exec urgp-api python -m urgp.db.seed

# ─────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────
test: ## Run all tests
	poetry run pytest tests/ -v --cov=src/urgp --cov-report=term-missing

test-unit: ## Run unit tests only
	poetry run pytest tests/unit/ -v

test-integration: ## Run integration tests only (requires docker compose up)
	poetry run pytest tests/integration/ -v -m integration

# ─────────────────────────────────────────────
# Code Quality
# ─────────────────────────────────────────────
lint: ## Run linter (ruff)
	poetry run ruff check .

format: ## Format code (ruff)
	poetry run ruff format .

type-check: ## Run type checker (mypy)
	poetry run mypy src/

check: lint type-check test-unit ## Run all checks (lint + type-check + unit tests)

# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────
clean: ## Remove build artifacts, caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

install: ## Install project dependencies with Poetry
	poetry install

pre-commit-install: ## Install pre-commit hooks
	poetry run pre-commit install

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
