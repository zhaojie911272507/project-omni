# Project Omni Makefile
# Common development commands for quick access

.PHONY: help install test lint format typecheck precommit clean \
        docker-build docker-run docker-logs run-cli run-server dev

# Default target
help:
	@echo "Project Omni - Available Commands"
	@echo "=================================="
	@echo ""
	@echo "  make install       - Install dependencies from requirements.txt"
	@echo "  make install-dev   - Install with development dependencies"
	@echo "  make test          - Run pytest test suite"
	@echo "  make test-cov      - Run tests with coverage report"
	@echo "  make lint          - Run ruff linter"
	@echo "  make format        - Format code with ruff"
	@echo "  make format-check  - Check code formatting (no changes)"
	@echo "  make typecheck     - Run mypy type checker"
	@echo "  make precommit     - Run all pre-commit checks"
	@echo "  make clean         - Remove cache files and build artifacts"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make docker-logs   - View Docker container logs"
	@echo "  make run-cli       - Run CLI agent"
	@echo "  make run-server    - Run FastAPI server"
	@echo "  make dev           - Run server with auto-reload"
	@echo ""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Installation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Done!"

install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov ruff mypy pre-commit
	@echo "Done!"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Testing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

test:
	@echo "Running tests..."
	pytest tests/

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/"

test-watch:
	@echo "Running tests in watch mode..."
	pytest tests/ -w

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Code Quality
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

lint:
	@echo "Running linter..."
	ruff check .

lint-fix:
	@echo "Running linter with auto-fix..."
	ruff check . --fix

format:
	@echo "Formatting code..."
	ruff format .

format-check:
	@echo "Checking code format..."
	ruff format . --check

typecheck:
	@echo "Running type checker..."
	mypy . --ignore-missing-imports --no-strict-optional

precommit:
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cleanup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true
	@echo "Cleaned!"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Docker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

docker-build:
	@echo "Building Docker image..."
	docker build -t project-omni:latest .

docker-run:
	@echo "Running Docker container..."
	docker compose up -d

docker-stop:
	@echo "Stopping Docker container..."
	docker compose down

docker-logs:
	@echo "Showing Docker container logs..."
	docker compose logs -f omni

docker-rebuild:
	@echo "Rebuilding and restarting Docker container..."
	docker compose up -d --build

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run Application
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

run-cli:
	@echo "Starting CLI agent..."
	python main.py

run-server:
	@echo "Starting FastAPI server on port 8000..."
	uvicorn server:app --host 0.0.0.0 --port 8000

dev:
	@echo "Starting development server with auto-reload..."
	uvicorn server:app --reload --host 0.0.0.0 --port 8000

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

setup-venv:
	@echo "Setting up virtual environment..."
	python -m venv .venv
	@echo "Virtual environment created!"
	@echo "Run: source .venv/bin/activate"

setup-precommit:
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "Pre-commit hooks installed!"

setup-browser:
	@echo "Installing Playwright browsers..."
	playwright install chromium
	@echo "Done!"

setup: setup-venv install-dev setup-precommit setup-browser
	@echo ""
	@echo "Setup complete!"
	@echo "Run: source .venv/bin/activate"
