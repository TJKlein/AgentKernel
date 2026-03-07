# Examples and Default Setup

## Default setup

- **Config source**: Environment variables (and optional `config.yaml`). Loaded via `config.loader.load_config()` or `mcpruntime.create_agent()` (which calls it when `config=None`).
- **Sandbox**: `SANDBOX_TYPE` defaults to **`opensandbox`**. The only supported execution backend is **OpenSandbox** (Docker via `opensandbox-server`).
- **Paths**: `WORKSPACE_DIR=./workspace`, `SKILLS_DIR=./skills`; servers from config/env.
- **LLM**: Disabled by default (`LLM_CODE_GENERATION=false`). Set `LLM_CODE_GENERATION=true` or provide Azure/OpenAI env vars for code generation.
- **create_agent()**: Always uses `OpenSandboxExecutor`; ignores `sandbox_type` other than `opensandbox`/`docker` (logs a warning and still uses OpenSandbox).

## Prerequisites to run examples

1. **OpenSandbox**: `pip install opensandbox opensandbox-server`, then `opensandbox-server init-config ~/.sandbox.toml --example docker` and `opensandbox-server start` (Docker running).
2. **LLM** (for examples that generate code): Set `OPENAI_API_KEY` or Azure env vars; optionally `LLM_CODE_GENERATION=true` or pass `llm_enabled=True` to `create_agent()`.

## Example index

| Example | Purpose | Backend / API | Notes |
|--------|---------|----------------|-------|
| **00_simple_api.py** | Minimal `create_agent()` / `execute_task()` | Default (OpenSandbox) | Prerequisites updated to OpenSandbox. |
| **00_minimal_monty.py** | Minimal agent (default backend) | OpenSandbox | Uses `create_agent()` with default config; same as 00_simple_api but single task. |
| **01–08** | Tool chains, state, skills, filesystem, etc. | OpenSandboxExecutor | Use `load_config()` + `OpenSandboxExecutor` (or `create_agent()`). |
| **09_configuration.py** | Programmatic LLM/state config | Default (OpenSandbox) | Uses `create_agent()` with kwargs only. |
| **10, 11, 12, 13, 14** | MCP server/client, statefulness | Server/OpenSandbox | Depend on server config and OpenSandbox. |
| **15_recursive_agent.py** | RLM (infinite context) | OpenSandbox + RecursiveAgent | Uses OpenSandboxExecutor + RecursiveAgent. |
| **16_recursive_agent_with_tools.py** | RLM + tools | OpenSandbox + RecursiveAgent | Same as 15 with tools. |
| **17_skill_evolution.py** | Self-growing tool library | OpenSandboxExecutor | Uses OpenSandbox; requires `opensandbox-server start`. |
| **18_streaming.py** | Streaming execution | Default | Uses `create_agent()` / streaming API. |
| **19_replay.py** | Replay / time-travel | Default | Uses `create_agent()`. |

## Removed / unavailable

- **SandboxExecutor** and **MicrosandboxExecutor** from `client.sandbox_executor`: that module was removed; all such examples now use **OpenSandboxExecutor**.
- **Monty** as recommended backend: MontyExecutor still exists for legacy use, but the default and supported backend is OpenSandbox only.
