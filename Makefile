.PHONY: help install install-dev generate test test-phase0 test-phase1 test-phase2 test-phase3 test-phase4 lint fmt typecheck clean docker-up docker-down

PYTHON := uv run python
PYTEST := uv run pytest
RUFF   := uv run ruff
MYPY   := uv run mypy

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime dependencies with uv
	uv sync

install-dev:  ## Install all dependencies including dev extras
	uv sync --extra dev

generate:  ## Generate sample data for all 4 modalities
	$(PYTHON) -m ch6_multimodal_perception.data_generator

test:  ## Run full test suite
	$(PYTEST) tests/ --cov=src --cov-report=term-missing

test-phase0:  ## Run Phase 0 foundation tests
	$(PYTEST) tests/test_phase0_foundation.py -v

test-phase1:  ## Run Phase 1 config and models tests
	$(PYTEST) tests/test_phase1_config.py -v

test-phase2:  ## Run Phase 2 extractor tests
	$(PYTEST) tests/test_phase2_extractors.py -v

test-phase3:  ## Run Phase 3 embedding and retrieval tests
	$(PYTEST) tests/test_phase3_retrieval.py -v

test-phase4:  ## Run Phase 4 pipeline and handoff tests
	$(PYTEST) tests/test_phase4_pipeline.py -v

lint:  ## Run ruff linter
	$(RUFF) check src/ tests/

fmt:  ## Format code with ruff
	$(RUFF) format src/ tests/

typecheck:  ## Run mypy type checker
	$(MYPY) src/

clean:  ## Remove generated artifacts
	rm -rf data/samples/ __pycache__ .pytest_cache .mypy_cache dist build *.egg-info
	migrations/versions/*.py 2>/dev/null || true

docker-up:  ## Start Qdrant and NeonDB services
	docker compose up -d

docker-down:  ## Stop all services
	docker compose down

migrate:  ## Run Alembic database migrations
	uv run alembic upgrade head

migrate-gen:  ## Auto-generate new migration
	uv run alembic revision --autogenerate -m "$(MSG)"
