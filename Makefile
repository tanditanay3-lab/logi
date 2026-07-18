# Lanework Makefile
# This Makefile provides common development and deployment tasks

.PHONY: help install test lint format clean docker-up docker-down docker-build docker-push migrate seed

# Default target
help:
	@echo "Lanework Makefile"
	@echo ""
	@echo "Development:"
	@echo "  make install          - Install Python dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make lint             - Run linting"
	@echo "  make format           - Format code"
	@echo "  make clean            - Clean build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        - Start all services with Docker Compose"
	@echo "  make docker-down      - Stop all services"
	@echo "  make docker-build     - Build Docker images"
	@echo "  make docker-push      - Push Docker images to registry"
	@echo ""
	@echo "Database:"
	@echo "  make migrate          - Run database migrations"
	@echo "  make seed             - Seed the database with test data"

# Python environment
PYTHON ?= python3
PIP ?= pip3
POETRY ?= poetry

# Install dependencies
install:
	$(POETRY) install --no-interaction --no-ansi

# Run tests
test:
	$(POETRY) run pytest tests/ -v --cov=apps --cov=packages --cov-report=term-missing

# Run specific tests
test-unit:
	$(POETRY) run pytest tests/unit/ -v

test-integration:
	$(POETRY) run pytest tests/integration/ -v

test-e2e:
	$(POETRY) run pytest tests/e2e/ -v

# Linting
lint:
	$(POETRY) run ruff check apps/ packages/
	$(POETRY) run mypy apps/ packages/

# Formatting
format:
	$(POETRY) run black apps/ packages/
	$(POETRY) run ruff check --fix apps/ packages/

# Clean
clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-push:
	docker-compose push

docker-logs:
	docker-compose logs -f

docker-ps:
	docker-compose ps

# Database migrations
migrate:
	$(POETRY) run alembic upgrade head

migrate-make name="":
	$(POETRY) run alembic revision --autogenerate -m "$(name)"

migrate-downgrade:
	$(POETRY) run alembic downgrade -1

# Database seeding
seed:
	$(POETRY) run python scripts/seed_database.py

# Run services locally
dev:
	@echo "Starting development servers..."
	@echo "API Gateway: http://localhost:8080"
	@echo "Orchestrator: http://localhost:8000"
	@echo "Shipment Tracking: http://localhost:8001"
	@echo ""
	$(POETRY) run uvicorn apps.api_gateway.main:app --reload --port 8080 &
	$(POETRY) run uvicorn apps.orchestrator.main:app --reload --port 8000 &
	$(POETRY) run uvicorn agents.shipment_tracking.main:app --reload --port 8001 &
	wait

# Run a single service
dev-api-gateway:
	$(POETRY) run uvicorn apps.api_gateway.main:app --reload --port 8080

dev-orchestrator:
	$(POETRY) run uvicorn apps.orchestrator.main:app --reload --port 8000

dev-shipment-tracking:
	$(POETRY) run uvicorn agents.shipment_tracking.main:app --reload --port 8001

dev-inventory:
	$(POETRY) run uvicorn agents.inventory_management.main:app --reload --port 8002

dev-route-optimization:
	$(POETRY) run uvicorn agents.route_optimization.main:app --reload --port 8003

# Shell
shell:
	$(POETRY) run python -i -c "from lanework import *; print('Lanework loaded')"

# Open API docs
open-api:
	@echo "Opening API documentation..."
	@echo "API Gateway: http://localhost:8080/docs"
	@echo "Orchestrator: http://localhost:8000/docs"
	@echo "Shipment Tracking: http://localhost:8001/docs"
