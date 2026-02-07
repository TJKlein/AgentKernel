# Changelog

All notable changes to this project will be documented in this file.

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
