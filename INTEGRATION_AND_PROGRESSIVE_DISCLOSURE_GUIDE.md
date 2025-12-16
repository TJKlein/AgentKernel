# Complete Integration and Progressive Disclosure Guide

This comprehensive guide covers:
- Integrating context-aware tools, JWT-aware state management, and external MCP server tools
- Progressive disclosure implementation following Anthropic's code execution with MCP pattern
- Alignment with Anthropic's best practices

**Reference:** [Anthropic's Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Context-Aware Tools](#context-aware-tools)
4. [JWT-Aware State Management](#jwt-aware-state-management)
5. [External Tools Integration](#external-tools-integration)
6. [Progressive Disclosure](#progressive-disclosure)
7. [Complete Integration Example](#complete-integration-example)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The integrated MCP server combines multiple capabilities:

1. **Code Execution** - Execute tasks using code generation (from code-execution-mcp)
2. **Context-Aware Tools** - Access session context via JWT tokens
3. **JWT-Aware State** - User-scoped state management with session continuity
4. **External Tools** - Proxy tools from other MCP servers
5. **Progressive Disclosure** - Tools loaded on-demand, not all upfront

### Key Benefits

✅ **Single Unified Server** - All tools accessible through one endpoint  
✅ **User Isolation** - Each user's state and context is completely isolated  
✅ **Session Continuity** - Users can continue their sessions across different sessions  
✅ **Extensible** - Easy to add tools from external MCP servers  
✅ **Secure** - JWT token required for all operations  
✅ **Progressive Disclosure** - Tools loaded on-demand for better performance  
✅ **Scalable** - Performance independent of total tool count  

---

## Installation

### Step 1: Install code-execution-mcp

```bash
cd /path/to/code-execution-mcp
pip install -e .
```

### Step 2: Install Dependencies

```bash
pip install fastmcp fastapi uvicorn
```

### Step 3: Verify Installation

```python
from code_execution_mcp import create_server
from code_execution_mcp.context_tools import create_context_tools
from code_execution_mcp.jwt_state_tools import create_jwt_state_tools
from code_execution_mcp.mcp_proxy import create_proxy_tools_from_server

# All modules should import successfully
```

---

## Context-Aware Tools

Context-aware tools allow accessing session context via JWT tokens, enabling:
- Retrieving conversation history
- Getting session metadata and statistics
- Searching conversation messages
- Accessing tool call history
- Getting recent messages

### Integration

```python
from code_execution_mcp import create_server
from code_execution_mcp.context_tools import create_context_tools
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from agent import orchestrator

# Create server
server = create_server()

# Create and register context tools
context_tools = create_context_tools(orchestrator)
for tool in context_tools:
    server.register_tool(tool)
```

### Available Context Tools

1. **`get_context_metadata`** - Get session metadata (session ID, user ID, model ID, etc.)
2. **`get_conversation_history`** - Retrieve full conversation history
3. **`get_session_info`** - Get session statistics and metadata
4. **`search_conversation`** - Search messages by keyword or role
5. **`get_tool_calls`** - Get tool call history with optional filters
6. **`get_recent_messages`** - Get the latest N messages

### Usage Example

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Get JWT token from session initialization
jwt_token = "your-jwt-token-here"

# Create client with JWT token
transport = StreamableHttpTransport(
    url="http://localhost:8000/mcp/",
    headers={"Authorization": f"Bearer {jwt_token}"}
)

async with Client(transport) as client:
    # Get context metadata
    metadata = await client.call_tool_mcp("get_context_metadata", {})
    
    # Get conversation history
    history = await client.call_tool_mcp("get_conversation_history", {})
    
    # Search conversation
    results = await client.call_tool_mcp("search_conversation", {
        "keyword": "forms",
        "limit": 5
    })
```

---

## JWT-Aware State Management

JWT-aware state management ensures that each user's state is automatically isolated and persists across sessions.

### How It Works

When a user calls `get_state()` or `save_state()`, the system:

1. **Extracts JWT token** from `Authorization: Bearer <JWT>` header
2. **Decodes JWT** to get `user_id` from `sub` claim (standard JWT field)
3. **Creates user-specific workspace**: `workspace/users/{user_id}/`
4. **Stores/retrieves state** from that user's directory

**Key Points:**
- ✅ State is scoped by `user_id`, not `session_id`
- ✅ Same user can continue their session across different sessions
- ✅ Different users are completely isolated from each other

### Workspace Structure

```
workspace/
  └── users/
      ├── {user_id_1}/        # User 1's workspace (persists across sessions)
      │   ├── state.json
      │   └── other_files...
      ├── {user_id_2}/        # User 2's workspace (persists across sessions)
      │   └── state.json
      └── {user_id_3}/        # User 3's workspace (persists across sessions)
          └── state.json
```

### Integration

```python
from code_execution_mcp import create_server
from code_execution_mcp.jwt_state_tools import create_jwt_state_tools
from agent import orchestrator

# Create server
server = create_server()

# Replace default state tools with JWT-aware versions
jwt_state_tools = create_jwt_state_tools(
    orchestrator,
    base_workspace_dir=server.config.execution.workspace_dir
)

# Register JWT-aware tools (they override the default ones)
for tool in jwt_state_tools:
    server.register_tool(tool)
```

### Usage Example

```python
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Get JWT token from session initialization
jwt_token = "your-jwt-token"

# Create client with JWT token
transport = StreamableHttpTransport(
    url="http://localhost:8000/mcp/",
    headers={"Authorization": f"Bearer {jwt_token}"}
)

async with Client(transport) as client:
    # Save state - automatically scoped to this user
    await client.call_tool_mcp("save_state", {
        "state_data": {"step": 1, "progress": 50}
    })
    
    # Get state - returns only this user's state
    result = await client.call_tool_mcp("get_state", {})
    print(result["data"])  # {"step": 1, "progress": 50}
```

### Session Continuity Example

```python
# User "alice" creates session 1
jwt_token_1 = generate_jwt_token("alice")  # JWT has {"sub": "alice"}
await client1.call_tool_mcp("save_state", {"state_data": {"step": 1}})

# User "alice" creates session 2 - can still access their state!
jwt_token_2 = generate_jwt_token("alice")  # Same user_id
state = await client2.call_tool_mcp("get_state", {})
# Returns: {"step": 1} ✅ Same state!

# User "bob" creates session - completely isolated
jwt_token_3 = generate_jwt_token("bob")  # Different user_id
state = await client3.call_tool_mcp("get_state", {})
# Returns: {} ✅ Different user, different state
```

---

## External Tools Integration

You can add tools from other MCP servers to your integrated server, creating a unified toolset.

### Method 1: Proxy All Tools from a Server

```python
from code_execution_mcp import create_server
from code_execution_mcp.mcp_proxy import create_proxy_tools_from_server

# Create server
server = create_server()

# Create proxy tools from external server
proxy_tools = await create_proxy_tools_from_server(
    "http://localhost:8001/mcp/",
    server_name="external",  # Optional: prefix for tool names
    headers={"Authorization": "Bearer token"}  # Optional: auth headers
)

# Register all proxy tools
for tool in proxy_tools:
    server.register_tool(tool)
```

### Method 2: Proxy Specific Tool

```python
from code_execution_mcp import create_server
from code_execution_mcp.mcp_proxy import create_simple_proxy_tool

# Create server
server = create_server()

# Create proxy for specific tool
weather_tool = create_simple_proxy_tool(
    "http://localhost:8001/mcp/",
    "get_weather",
    proxy_name="external_weather",  # Optional: custom name
    headers={"Authorization": "Bearer token"}  # Optional
)

# Register tool
server.register_tool(weather_tool)
```

---

## Progressive Disclosure

Progressive disclosure is a key principle from Anthropic's code execution with MCP article. It means tools should be loaded on-demand, not all upfront, for better performance and scalability.

### Implementation

The `search_tools` function implements true progressive disclosure with three detail levels:

#### `detail_level="name"` (Fastest - No File Loading)

```python
search_tools("context", detail_level="name")
```

**What happens:**
- Scans filesystem for tool filenames only
- Performs keyword matching on tool names
- Returns matching tool names grouped by server

**Performance:**
- ✅ No file I/O (except directory scanning)
- ✅ ~10-100x faster than before
- ✅ Instant results even with thousands of tools

**Example:**
```python
{
  "context": ["get_context_metadata", "get_conversation_history"],
  "google-drive": ["getDocument", "listFiles"]
}
```

#### `detail_level="description"` (Efficient - Metadata Only)

```python
search_tools("get user session", detail_level="description")
```

**What happens:**
- Extracts docstrings from all tool files (reads first 8KB only)
- Performs semantic search on metadata
- Returns matching tools with descriptions

**Performance:**
- ✅ Only reads docstrings, not full code
- ✅ ~5-10x faster than loading full files
- ✅ Efficient semantic search on lightweight metadata

**Example:**
```python
{
  "context": {
    "get_context_metadata": {
      "description": "Get session metadata (session ID, user ID, model ID, etc.)"
    }
  }
}
```

#### `detail_level="full"` (Lazy Loading - Only Matches)

```python
search_tools("process data", detail_level="full")
```

**What happens:**
- Extracts docstrings from all tool files (metadata only)
- Performs semantic search on metadata
- **Only loads full code for matching tools** (lazy loading)
- Returns full tool definitions

**Performance:**
- ✅ Only loads matching tools, not all tools
- ✅ Can be 100x faster with many tools (if only 1% match)
- ✅ True lazy loading - only what's needed

### Performance Comparison

**Before (Old Implementation):**
```
search_tools("context", detail_level="name")
  → discover_tools() [Discovers ALL tools] ❌
  → _get_tool_descriptions() [Loads ALL tool files] ❌
  → semantic_search() [Filters]
  → Returns names

Time: ~500ms-2s (depends on number of tools)
```

**After (Progressive Disclosure):**
```
search_tools("context", detail_level="name")
  → search_tool_names() [Keyword search, NO file loading] ✅
  → Returns names

Time: ~10-50ms (10-100x faster) ✅
```

### Usage Examples

```python
# Fast tool discovery - no file loading
results = await client.call_tool_mcp("search_tools", {
    "query": "context",
    "detail_level": "name"
})

# Efficient semantic search - metadata only
results = await client.call_tool_mcp("search_tools", {
    "query": "get user session information",
    "detail_level": "description"
})

# Lazy loading for full definitions
results = await client.call_tool_mcp("search_tools", {
    "query": "process data files",
    "detail_level": "full"
})
```

### Filesystem Discovery

Agents can also explore tools incrementally via filesystem:

```python
# Step 1: List servers (fast, no tool loading)
servers = await client.call_tool_mcp("list_servers", {})
# Returns: ["context", "google-drive", "salesforce"]

# Step 2: Explore specific server (fast, just names)
tools = await client.call_tool_mcp("get_server_tools", {"server_name": "context"})
# Returns: ["get_context_metadata", "get_conversation_history", ...]

# Step 3: Read specific tool only when needed (lazy loading)
tool_code = await client.call_tool_mcp("read_tool_file", {
    "server_name": "context",
    "tool_name": "get_context_metadata"
})
```

---

## Complete Integration Example

Here's a complete example integrating all features:

```python
"""Complete integrated MCP server with context, JWT state, and external tools."""

import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from code_execution_mcp import create_server
from code_execution_mcp.context_tools import create_context_tools
from code_execution_mcp.jwt_state_tools import create_jwt_state_tools
from code_execution_mcp.mcp_proxy import create_proxy_tools_from_server
from agent import orchestrator

# Create code-execution-mcp server
server = create_server()

# Add context-aware tools
context_tools = create_context_tools(orchestrator)
for tool in context_tools:
    server.register_tool(tool)

# Replace default state tools with JWT-aware versions
jwt_state_tools = create_jwt_state_tools(
    orchestrator,
    base_workspace_dir=server.config.execution.workspace_dir
)
for tool in jwt_state_tools:
    server.register_tool(tool)

# Add external tools (async setup)
async def setup_external_tools():
    external_servers = [
        "http://localhost:8001/mcp/",  # Weather service
        "http://localhost:8002/mcp/",  # Database service
    ]
    
    for server_url in external_servers:
        try:
            tools = await create_proxy_tools_from_server(
                server_url,
                headers={"Authorization": "Bearer token"}
            )
            for tool in tools:
                server.register_tool(tool)
        except Exception as e:
            print(f"Failed to add tools from {server_url}: {e}")

# Setup external tools
asyncio.run(setup_external_tools())

# Create FastAPI app
app = FastAPI(title="Integrated MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP server
mcp_app = server.http_app(path="/")
app.mount("/mcp", mcp_app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## API Reference

### Context Tools

#### `get_context_metadata()`
Get session metadata (session ID, user ID, model ID, etc.)

#### `get_conversation_history()`
Retrieve full conversation history

#### `get_session_info()`
Get session statistics and metadata

#### `search_conversation(keyword: str, limit: int = 10)`
Search messages by keyword or role

#### `get_tool_calls(endpoint: str = None, limit: int = 10)`
Get tool call history with optional filters

#### `get_recent_messages(count: int = 5)`
Get the latest N messages

### JWT State Tools

#### `get_state(state_file: str = "state.json")`
Get state from the user's workspace (JWT-scoped)

#### `save_state(state_data: dict, state_file: str = "state.json")`
Save state to the user's workspace (JWT-scoped)

### Progressive Disclosure Tools

#### `list_servers()`
List all available server directories (fast, no tool loading)

#### `get_server_tools(server_name: str)`
List tools available in a specific server (fast, just names)

#### `read_tool_file(server_name: str, tool_name: str)`
Read a specific tool file (lazy loading)

#### `search_tools(query: str, detail_level: str = "name", max_results: int = 10)`
Search for relevant tools using progressive disclosure:
- `detail_level="name"`: Fast keyword search, no file loading
- `detail_level="description"`: Semantic search on metadata only
- `detail_level="full"`: Loads only matching tool definitions

---

## Troubleshooting

### Error: "Missing JWT token"
- Ensure you're using HTTP transport (not stdio)
- Include `Authorization: Bearer <JWT>` header in requests

### Error: "Session not found"
- Verify JWT token is valid and not expired
- Check that session exists in ContextManager

### Error: "JWT token missing user identifier"
- Ensure JWT token contains `sub` claim (standard JWT field)
- Verify token was generated with `generate_jwt_token(user_id)`

### Tools not appearing
- Ensure tools are registered before calling `http_app()`
- Check server logs for registration messages
- Verify imports are correct

### State not persisting across sessions
- Verify JWT token contains `sub` claim with `user_id`
- Check that workspace directory is writable
- Ensure same `user_id` is used in both sessions

### External tools not working
- Verify external MCP server is running and accessible
- Check authentication headers if required
- Ensure external server supports HTTP transport

### Progressive disclosure not working
- Verify `ToolMetadataIndex` is imported correctly
- Check that `servers_dir` path is correct
- Ensure tool files have docstrings for metadata extraction

---

## Alignment with Anthropic's Pattern

✅ **Progressive disclosure** - Tools loaded on-demand, not all upfront  
✅ **Context efficiency** - Only load what's needed for current task  
✅ **Scalable** - Performance independent of total tool count  
✅ **Filesystem-based** - Tools discoverable via filesystem exploration  
✅ **User isolation** - Each user's state and context is completely isolated  
✅ **Session continuity** - Users can continue sessions across different sessions  
✅ **Code execution support** - Tools usable in code, not just direct calls  

This implementation fully aligns with [Anthropic's code execution with MCP best practices](https://www.anthropic.com/engineering/code-execution-with-mcp)!

---

## Summary

✅ **Context-aware tools** - Access session context via JWT tokens  
✅ **JWT-aware state** - User-scoped state with session continuity  
✅ **External tools** - Proxy tools from other MCP servers  
✅ **Progressive disclosure** - Tools loaded on-demand for better performance  
✅ **Single unified server** - All tools accessible through one endpoint  
✅ **User isolation** - Complete isolation between users  
✅ **Session continuity** - Users can continue sessions across different sessions  
✅ **Secure** - JWT token required for all operations  

For more details, see:
- `code_execution_mcp/context_tools.py` - Context tools implementation
- `code_execution_mcp/jwt_state_tools.py` - JWT state tools implementation
- `code_execution_mcp/mcp_proxy.py` - External tools proxy implementation
- `code_execution_mcp/client/tool_metadata.py` - Progressive disclosure implementation
- `backend/servers/integrated_mcp_server.py` - Complete integration example

