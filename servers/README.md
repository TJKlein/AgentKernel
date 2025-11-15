# Example MCP Servers

This directory contains example tool files that demonstrate the filesystem-based tool discovery pattern. Each subdirectory represents an MCP server, and contains Python modules that wrap MCP tool calls.

## Structure

Each server directory follows this structure:

```
servers/
├── <server_name>/
│   ├── __init__.py          # Index file that imports and exports all tools
│   ├── <tool_name>.py       # Individual tool files (one per tool)
│   └── ...
```

## Example Servers

### Weather Server (`weather/`)

Provides weather-related tools:
- `get_weather(location: str, units: Optional[str] = None)` - Get current weather
- `get_forecast(location: str, days: Optional[int] = None, units: Optional[str] = None)` - Get weather forecast

### Filesystem Server (`filesystem/`)

Provides file system operations:
- `read_file(path: str, encoding: Optional[str] = None)` - Read file contents
- `write_file(path: str, content: str, encoding: Optional[str] = None)` - Write file contents
- `list_directory(path: str, recursive: Optional[bool] = None)` - List directory contents

### Calculator Server (`calculator/`)

Provides mathematical operations:
- `add(a: float, b: float)` - Add two numbers
- `multiply(a: float, b: float)` - Multiply two numbers
- `calculate(expression: str)` - Evaluate a mathematical expression

### Database Server (`database/`)

Provides database operations:
- `query(sql: str, parameters: Optional[List[Any]] = None)` - Execute a SQL query
- `execute(sql: str, parameters: Optional[List[Any]] = None)` - Execute a SQL statement
- `list_tables()` - List all tables in the database

## Usage

These tool files are automatically discovered by the filesystem helper. Agents can import and use them in their code:

```python
# Example: Using weather tools
from servers.weather import get_weather, get_forecast

current_weather = get_weather(location="San Francisco, CA")
forecast = get_forecast(location="San Francisco, CA", days=5)
```

## Generating Tool Files

To generate tool files from actual MCP servers, use the tool generation script:

```bash
python scripts/generate_tool_files.py
```

This will connect to configured MCP servers and generate tool files based on their available tools.

## Adding New Servers

To add a new example server:

1. Create a new directory under `servers/` (e.g., `servers/my_server/`)
2. Create tool files (`.py`) for each tool
3. Create an `__init__.py` file that imports and exports all tools
4. Follow the pattern shown in existing servers

Each tool file should:
- Import `call_mcp_tool` from `client.mcp_client`
- Define a function with proper type hints
- Call `call_mcp_tool` with the server name, tool name, and parameters
- Include a docstring describing what the tool does

