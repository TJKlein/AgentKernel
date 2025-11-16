# Code Execution MCP Implementation

A generic, extensible code execution pattern for MCP (Model Context Protocol) that allows agents to interact with MCP servers through Python code APIs instead of direct tool calls. This significantly reduces token consumption and improves efficiency by leveraging LLMs' strength at writing code.

**📖 For complete documentation, see [DOCUMENTATION.md](./DOCUMENTATION.md)**

## Quick Start

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install and start Microsandbox server
curl -sSL https://get.microsandbox.dev | sh
msb server start --dev  # Keep running in separate terminal

# Run an example
python examples/01_basic_tool_call.py
```

## Features

- **Filesystem-based Tool Discovery**: Agents discover tools by exploring the `servers/` directory
- **State Persistence**: Save and resume work using the `workspace/` directory
- **Skills System**: Reusable code functions stored in `skills/` directory
- **Progressive Disclosure**: Only load tools that are needed
- **Secure Execution**: microsandbox integration for hardware-isolated execution

## Architecture

This implementation follows the [Anthropic article on code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp):

- ✅ Filesystem-based tool discovery
- ✅ Progressive disclosure
- ✅ State persistence via volume mounts
- ✅ Tools as filesystem modules
- ✅ Code execution pattern

See [DOCUMENTATION.md](./DOCUMENTATION.md) for detailed architecture analysis and compliance verification.

## Examples

See `examples/` directory for comprehensive examples:
- Basic tool calls
- Multi-tool chaining
- Data filtering
- Control flow
- State persistence
- Skills and reusable code

## Documentation

- **[DOCUMENTATION.md](./DOCUMENTATION.md)**: Complete documentation including:
  - Installation and setup
  - Architecture compliance analysis
  - Workspace and session management
  - Per-customer workspace support
  - Session continuity with logs
  - Examples guide
  - Configuration
  - Development guide

## License

MIT
