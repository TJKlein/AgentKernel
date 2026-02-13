# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Recursive Language Models (RLM)** support:
    - New `RecursiveAgent` capable of processing infinite context windows via "chunk-and-reason" loops.
    - Automatic tool inlining for Monty-based RLM agents.
    - Specific standard library tool mapping for Python-Monty.
- **Enhanced Testing Infrastructure**:
    - Centralized `tests/` directory with `unit`, `integration`, and `e2e` suites.
    - `conftest.py` fixtures for mocked and live LLM clients.
    - `tests/e2e/test_live_rlm.py` for validating RLM functionality against real LLMs (Azure/Standard).
- **Configuration**:
    - Added `.env` support for test configuration.
    - Added `.env.example` template.

### Fixed
- **Monty Executor**:
    - Fixed `TypeError` and validation errors when executing code with empty inputs.
    - Improved handling of `pydantic-monty` edge cases.
- **Code Generator**:
    - Fixed crash when `required_tools` is `None`.
- **Recursive Agent**:
    - Fixed `UnboundLocalError` by only injecting `CONTEXT_DATA` instructions when context is present.

### Changed
- Refactored `examples/` to move reusable verification logic into proper tests.

## [0.1.1] - 2026-02-07

### Added
- **Monty Execution Backend**: Integrated `pydantic-monty` as an experimental high-performance execution runtime.
- **Pluggable Executor Architecture**: Refactored `AgentHelper` to support multiple backends via `CodeExecutor` interface.
- **OS Callbacks for Monty**: Implemented file system redirection for Monty to allow workspace access.
- **JSON Helpers for Monty**: Injected `json_loads` and `json_dumps` to Monty environment.
- **Versioning Support**: Added `--version` flag to MCP server CLI and a `get_version` tool.

### Changed
- Refactored `SandboxExecutor` to `MicrosandboxExecutor`.
- Updated `create_agent` factory to handle dynamic backend selection.
- Patched `ToolSelector` to handle broken `torch` installations gracefully.

## [0.1.0] - 2026-01-30

### Added
- Initial release of AgentKernel.
- Support for Microsandbox execution.
- MCP tool discovery and selection using semantic search.
- Async middleware for background task execution.
- Programmatic Tool Calling (PTC) pattern implementation.
