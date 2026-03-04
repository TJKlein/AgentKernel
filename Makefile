# MCPRuntime — development and test commands.
# See CONTRIBUTING.md for setup and contribution guidelines.

.PHONY: help install install-dev env test test-unit test-e2e verify run-example

help:
	@echo "MCPRuntime — development commands"
	@echo ""
	@echo "  make install      Install the package (pip install -e .)"
	@echo "  make install-dev  Install with dev dependencies (pytest, ruff, etc.)"
	@echo "  make env          Copy .env.example to .env if missing"
	@echo "  make test         Run unit and integration tests (no API key required)"
	@echo "  make test-unit    Run unit tests only"
	@echo "  make test-e2e     Run end-to-end tests (requires .env with API keys)"
	@echo "  make test-all     Run full test suite"
	@echo "  make verify       Run setup verification (microsandbox/MCPRuntime)"
	@echo "  make run-example  Run examples/00_simple_api.py"
	@echo ""

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example — add your API keys."; else echo ".env already exists."; fi

test:
	pytest tests/ -v -m "not live" --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-e2e:
	pytest tests/e2e/ -v --tb=short

test-all:
	pytest tests/ -v --tb=short

verify:
	python verify_setup.py

run-example:
	python examples/00_simple_api.py
