# Payslip Intelligence Suite - Makefile
# 
# This Makefile provides convenient commands for development, testing,
# and deployment of the Payslip Intelligence Suite.
# All operations use a virtual environment to keep your system clean.

.PHONY: help venv install test lint format typecheck run setup clean dev-setup activate

# Virtual environment settings
VENV_NAME = venv
VENV_PATH = ./$(VENV_NAME)
PYTHON = $(VENV_PATH)/bin/python
PIP = $(VENV_PATH)/bin/pip
PYTEST = $(VENV_PATH)/bin/pytest
BLACK = $(VENV_PATH)/bin/black
FLAKE8 = $(VENV_PATH)/bin/flake8
MYPY = $(VENV_PATH)/bin/mypy

# Default target
help:
	@echo "Payslip Intelligence Suite - Available Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make venv        - Create virtual environment"
	@echo "  make install     - Install all dependencies in venv"
	@echo "  make dev-setup   - Set up complete development environment"
	@echo "  make setup       - Run interactive setup wizard"
	@echo "  make activate    - Show command to activate virtual environment"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run all tests with coverage"
	@echo "  make lint        - Run linting checks"
	@echo "  make format      - Format code with black"
	@echo "  make typecheck   - Run type checking with mypy"
	@echo "  make check       - Run all quality checks (lint + typecheck + test)"
	@echo ""
	@echo "Execution:"
	@echo "  make run         - Process documents (equivalent to 'python main.py ingest')"
	@echo "  make status      - Show system status"
	@echo "  make validate    - Validate configuration"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       - Clean up temporary files and caches"
	@echo "  make clean-all   - Clean everything including virtual environment"
	@echo "  make requirements - Update requirements.txt with current dependencies"
	@echo ""
	@echo "Note: All commands automatically use the virtual environment in ./$(VENV_NAME)/"

# Check if virtual environment exists
check-venv:
	@if [ ! -d "$(VENV_PATH)" ]; then \
		echo "❌ Virtual environment not found. Run 'make venv' first."; \
		exit 1; \
	fi

# Create virtual environment
venv:
	@if [ -d "$(VENV_PATH)" ]; then \
		echo "✅ Virtual environment already exists at $(VENV_PATH)"; \
	else \
		echo "🐍 Creating virtual environment..."; \
		python3 -m venv $(VENV_PATH); \
		echo "✅ Virtual environment created at $(VENV_PATH)"; \
		echo ""; \
		echo "To activate manually, run:"; \
		echo "  source $(VENV_PATH)/bin/activate"; \
	fi

# Installation and setup
install: check-venv
	@echo "📦 Installing dependencies in virtual environment..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev-setup: venv install
	@echo "🔧 Setting up development environment..."
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Virtual environment is located at: $(VENV_PATH)"

setup: check-venv
	@echo "🚀 Running interactive setup..."
	$(PYTHON) main.py setup

activate:
	@echo "To activate the virtual environment, run:"
	@echo "  source $(VENV_PATH)/bin/activate"
	@echo ""
	@echo "To deactivate later, simply run:"
	@echo "  deactivate"

# Code quality
test: check-venv
	@echo "🧪 Running tests with coverage..."
	$(PYTEST) tests/ -v --cov=services --cov-report=html --cov-report=term-missing
	@echo "📊 Coverage report generated in htmlcov/"

lint: check-venv
	@echo "🔍 Running linting checks..."
	$(FLAKE8) services/ main.py --max-line-length=100 --ignore=E203,W503
	@echo "✅ Linting complete!"

format: check-venv
	@echo "🎨 Formatting code with black..."
	$(BLACK) services/ main.py tests/ --line-length=100
	@echo "✅ Code formatted!"

typecheck: check-venv
	@echo "🔎 Running type checks..."
	$(MYPY) services/ main.py --ignore-missing-imports --no-strict-optional
	@echo "✅ Type checking complete!"

check: lint typecheck test
	@echo "✅ All quality checks passed!"

# Execution commands
run: check-venv
	@echo "🚀 Processing documents..."
	$(PYTHON) main.py ingest

run-verbose: check-venv
	@echo "🚀 Processing documents (verbose)..."
	$(PYTHON) main.py ingest --verbose

status: check-venv
	@echo "📊 Checking system status..."
	$(PYTHON) main.py status

validate: check-venv
	@echo "🔍 Validating configuration..."
	$(PYTHON) main.py validate-config

# Maintenance
clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	@echo "✅ Cleanup complete!"

clean-all: clean
	@echo "🧹 Removing virtual environment..."
	rm -rf $(VENV_PATH)
	@echo "✅ Virtual environment removed!"

requirements: check-venv
	@echo "📝 Updating requirements.txt..."
	$(PIP) freeze > requirements.txt.new
	@echo "⚠️  Review requirements.txt.new and replace requirements.txt if correct"

# Development helpers
watch-test: check-venv
	@echo "👀 Watching for changes and running tests..."
	$(PYTHON) -m pytest_watch tests/ -- -v

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t payslip-intelligence .

docker-run:
	@echo "🐳 Running in Docker container..."
	docker run -v $(PWD)/incoming_docs:/app/incoming_docs -v $(PWD)/archive:/app/archive -v $(PWD)/output:/app/output payslip-intelligence

# Documentation
docs:
	@echo "📚 Generating documentation..."
	@echo "Documentation structure:"
	@echo "  - README.md: Project overview and setup"
	@echo "  - config.toml: Configuration reference"
	@echo "  - services/: Core service modules"
	@echo "  - tests/: Comprehensive test suite"

# CI/CD helpers
ci-test: venv install test lint typecheck
	@echo "✅ CI/CD pipeline tests completed!"

# Quick start for new users
quickstart: dev-setup setup
	@echo ""
	@echo "🎉 Quick start complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Activate the virtual environment: source $(VENV_PATH)/bin/activate"
	@echo "  2. Add documents to the 'incoming_docs' folder"
	@echo "  3. Run 'make run' to process documents"
	@echo "  4. Check the 'output' folder for results"
	@echo ""
	@echo "For help: make help"