# Makefile for Heimdex project
# Provides convenient shortcuts for common Docker operations

.PHONY: help test test-api test-worker test-all test-coverage test-unit test-integration test-shell build up down logs clean

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Heimdex Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development commands
build: ## Build all Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

logs-api: ## Tail logs from API service
	docker compose logs -f api

logs-worker: ## Tail logs from worker service
	docker compose logs -f worker

restart: ## Restart all services
	docker compose restart

restart-api: ## Restart API service
	docker compose restart api

restart-worker: ## Restart worker service
	docker compose restart worker

clean: ## Stop services and remove volumes
	docker compose down -v
	rm -rf services/api/htmlcov services/worker/htmlcov

# Test commands
test: ## Run API tests (default)
	./scripts/test.sh api

test-api: ## Run API tests
	./scripts/test.sh api

test-worker: ## Run worker tests
	./scripts/test.sh worker

test-all: ## Run all tests
	./scripts/test.sh all

test-coverage: ## Run tests with HTML coverage report
	./scripts/test.sh --coverage api

test-unit: ## Run only unit tests
	./scripts/test.sh --unit api

test-integration: ## Run only integration tests
	./scripts/test.sh --integration api

test-shell: ## Open shell in test container for debugging
	./scripts/test.sh --shell api

test-verbose: ## Run tests with verbose output
	./scripts/test.sh --verbose api

# Development workflow shortcuts
dev: up ## Start development environment

dev-rebuild: ## Rebuild and restart development environment
	docker compose up -d --build

dev-fresh: clean build up ## Fresh start (clean + build + up)

# Quick test during development
quick-test: ## Quick test (unit tests only, no coverage)
	./scripts/test.sh --unit api

# CI/CD simulation
ci: ## Run full CI pipeline locally (build + test + coverage)
	@echo "Running CI pipeline..."
	docker compose build
	./scripts/test.sh --coverage all
	@echo "✓ CI pipeline completed successfully"
