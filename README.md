# Code Execution MCP Implementation

A generic, extensible code execution pattern for MCP (Model Context Protocol) that allows agents to interact with MCP servers through Python code APIs instead of direct tool calls. This significantly reduces token consumption and improves efficiency by leveraging LLMs' strength at writing code.

## Features

- **Filesystem-based Tool Discovery**: Agents discover tools by exploring the `servers/` directory, loading only what they need
- **State Persistence**: Save and resume work using the `workspace/` directory
- **Skills System**: Reusable code functions stored in `skills/` directory
- **Type Safety**: Full type hints, mypy strict mode, runtime validation
- **Guardrails**: Comprehensive security, privacy, and business logic validation
- **Workflow System**: Configuration-driven workflows with YAML/JSON definitions
- **Form Filling**: Specialized support for form filling workflows
- **Extensible**: Plugin-based architecture for easy extension
- **Secure**: microsandbox integration for hardware-isolated execution

## Installation

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install
```

### Microsandbox Server Setup

The code execution requires a Microsandbox server to be running. The `msb` CLI tool needs to be installed separately from the Python package.

**Install the Microsandbox CLI**:
```bash
curl -sSL https://get.microsandbox.dev | sh
```

After installation, verify it's working:
```bash
msb --version
```

**Start the Microsandbox Server**:
```bash
msb server start --dev
```
Keep this running in a separate terminal. The server runs on `localhost:5555` by default.

**Alternative: Configure server URL via environment variable** (if using an existing server):
```bash
export MSB_SERVER_URL=http://localhost:5555
```

**Platform Requirements**:
- **macOS**: Requires Apple Silicon (M1/M2/M3/M4). Intel Macs are not supported.
- **Linux**: Requires KVM virtualization enabled. Check with: `lsmod | grep kvm`
- **Windows**: Support coming soon

**Note**: The server must be running before executing code examples.

## Quick Start

1. **Set up virtual environment** (if not already done):
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Install and start the Microsandbox server** (required for code execution):
```bash
# Install the CLI (one-time setup)
curl -sSL https://get.microsandbox.dev | sh

# Start the server (keep this running in a separate terminal)
msb server start --dev
```
The server runs on `localhost:5555` by default.

3. **Generate tool files from MCP servers**:
```bash
python scripts/generate_tool_files.py
```

4. **Run a simple example**:
```bash
python examples/01_basic_tool_call.py
```

5. **Execute a workflow**:
```bash
python -m workflows.executor --workflow examples/simple_workflow.yaml
```

## Project Structure

```
code-execution-mcp/
├── client/           # Core MCP client and sandbox executor
├── workflows/        # Workflow execution engine
├── config/           # Configuration management
├── plugins/          # Plugin system and examples
├── scripts/          # Tool generation scripts
├── servers/          # Generated tool files (filesystem-based discovery)
├── workspace/        # State persistence directory
├── skills/           # Reusable code functions
├── examples/         # Comprehensive showcase examples
├── tests/            # Test suite
└── docs/             # Additional documentation
```

## Examples

See the `examples/` directory for comprehensive examples covering:
- Basic tool calls
- Multi-tool chaining
- Data filtering and transformation
- Control flow and loops
- Workflows
- Form filling
- State persistence
- Skills and reusable code
- Progressive disclosure
- Privacy-preserving operations
- Custom workflows and plugins
- Complex multi-step workflows
- Comparison with traditional tool calling
- **Azure OpenAI integration** (examples 14-15)

## Configuration

1. Create a `.env` file in the project root
2. Configure your MCP servers and settings
3. For Azure OpenAI integration, add:
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` (optional, default: gpt-4o-mini)
   - `AZURE_OPENAI_API_VERSION` (optional, default: 2024-08-01-preview)
   - `AZURE_OPENAI_EMBEDDER_NAME` (optional, default: text-embedding-ada-002)
   - `AZURE_OPENAI_EMBEDDER_VERSION` (optional, default: 2023-05-15)

See `docs/azure_setup.md` for detailed Azure OpenAI configuration.

## Development

```bash
# Run tests
pytest

# Type checking
mypy .

# Linting
ruff check .

# Formatting
black .

# All checks
pre-commit run --all-files
```

## License

MIT

