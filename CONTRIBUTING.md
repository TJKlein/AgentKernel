# Contributing to AgentKernel

This document describes how to set up the development environment, run tests, and submit changes. For questions or discussions, please open an issue on GitHub.

## Before submitting the repository to GitHub

- Replace `TJKlein/agentkernel` with your actual GitHub org and repo name in: `README.md`, `CONTRIBUTING.md`, `DOCS.md`, `pyproject.toml`, and any workflow badge URLs.
- Ensure `.env` and `.codex/` are not tracked (they are in `.gitignore`). If they were ever committed, run `git rm -r --cached .env .codex 2>/dev/null; git commit -m "Stop tracking local config"` before pushing.
- Run `make test` (or `pytest tests/ -m "not live"`) to confirm tests pass.

## Repository layout

| Path | Purpose |
|------|---------|
| `agentkernel/` | Main package (public API, MCP, server). |
| `client/` | Agent helpers, executors, code generation, tools. |
| `config/` | Configuration schema and loader. |
| `server/` | MCP server implementation. |
| `tests/` | Test suite (`unit/`, `integration/`, `e2e/`). |
| `examples/` | Example scripts and usage patterns. |
| `servers/` | Sample MCP-style tool servers. |
| `docs/` | Reference docs (e.g. microsandbox patches). |
| `scripts/` | Development and CI helper scripts. |
| `verify_setup.py` | Setup verification (run from repo root). |

Run scripts from the repository root (e.g. `python scripts/check_setup.py`). Root-level `test_*.py` files are legacy or manual tests; the canonical suite is under `tests/`.

## Quick start

```bash
# 1. Clone the repo
git clone https://github.com/TJKlein/agentkernel.git
cd agentkernel

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install the package and dev dependencies
make install-dev
# or: pip install -e ".[dev]"

# 4. Copy env template and add your API key (optional for unit/integration tests)
make env
# Edit .env and set OPENAI_API_KEY or AZURE_OPENAI_* (see .env.example)

# 5. Run tests
make test          # Unit + integration (no API key needed)
make test-e2e      # E2E with real LLM (requires .env)
make test-all      # Full suite
```

## Commands (Makefile)

| Command | Description |
|--------|-------------|
| `make help` | Show all commands |
| `make install` | Install package |
| `make install-dev` | Install with pytest, ruff, etc. |
| `make env` | Copy `.env.example` → `.env` if missing |
| `make test` | Unit + integration tests |
| `make test-unit` | Unit tests only |
| `make test-e2e` | E2E (live) tests — needs API keys in `.env` |
| `make test-all` | Full test suite |
| `make verify` | Check microsandbox/setup |
| `make run-example` | Run `examples/00_simple_api.py` |

## Running tests without Make

```bash
# Unit + integration only (no API key)
pytest tests/ -v -m "not live"

# E2E (live) tests — set OPENAI_API_KEY or AZURE_OPENAI_* in .env
pytest tests/e2e/ -v

# Full suite
pytest tests/ -v
```

## Environment (.env)

Copy `.env.example` to `.env` and set the appropriate variables. The `.env` file is gitignored and must not be committed.

- **OpenAI:** `OPENAI_API_KEY`
- **Azure OpenAI:** `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`

E2E tests require a configured LLM; unit and integration tests do not. Do not add real API keys or server URLs to the repository; use placeholders in `.env.example` and documentation only.

## Microsandbox configuration (optional)

To run AgentKernel with the **microsandbox** runtime (MicroVM) instead of Monty:

1. **Clone and build microsandbox** (requires Rust):
   ```bash
   git clone https://github.com/TJKlein/microsandbox.git
   cd microsandbox
   cargo build --release
   ```
   This fork is required; the standard microsandbox distribution does not support volume mounting.

2. **Start the server** (in a separate terminal):
   ```bash
   cd /path/to/microsandbox
   ./target/release/msbserver --dev
   ```
   The server listens on `127.0.0.1:5555` by default.

3. **Verify setup** from the AgentKernel repo:
   ```bash
   make verify
   # or: python verify_setup.py
   ```

The default test backend is Monty; microsandbox is optional. Use microsandbox when you need full Linux isolation or volume mounting.

## Security and secrets

- Do not commit `.env`, `.env.local`, or any file containing API keys or server URLs.
- Use placeholders only in `.env.example`, documentation, and example configuration (e.g. `your-resource.cognitiveservices.azure.com`).
- The `.codex/` directory holds Codex (GitHub agent) model config and is gitignored. If it was previously tracked, run `git rm -r --cached .codex` and commit to remove it from the index.

## Code style

- Format: `black .` / `ruff check .`
- Type check: `mypy agentkernel client config server` (if mypy is installed)

## Getting help

Open an issue or discussion on GitHub for questions and contributions.
