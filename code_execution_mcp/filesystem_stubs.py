"""Filesystem stub generation for programmatically registered tools.

This module generates filesystem stubs for tools that are registered programmatically
(e.g., context tools, external tools) so they can be discovered and used via code
execution, following Anthropic's code execution with MCP pattern.

Reference: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

import os
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def generate_tool_stub(
    tool_func: Callable,
    server_name: str,
    tool_name: Optional[str] = None,
    import_path: str = "code_execution_mcp.client.mcp_client",
    client_var: str = "mcp_client",
) -> str:
    """Generate a filesystem stub file for a tool function.
    
    Creates a Python file that can be imported and used in code execution,
    following the pattern from Anthropic's code execution with MCP article.
    
    Args:
        tool_func: The tool function to generate a stub for
        server_name: Name of the server (directory name)
        tool_name: Optional tool name (defaults to function name)
        import_path: Path to import the MCP client from
        client_var: Variable name for the MCP client instance
    
    Returns:
        Python code as a string for the stub file
        
    Example:
        # Generate stub for context tool
        stub_code = generate_tool_stub(
            get_context_metadata,
            server_name="context",
            tool_name="get_context_metadata"
        )
        # Creates: servers/context/get_context_metadata.py
    """
    if tool_name is None:
        tool_name = tool_func.__name__
    
    # Get function signature
    sig = inspect.signature(tool_func)
    docstring = inspect.getdoc(tool_func) or f"Call {tool_name} tool"
    
    # Build parameters
    params = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        param_str = param_name
        if param.annotation != inspect.Parameter.empty:
            # Convert type annotation to string
            ann_str = str(param.annotation)
            # Simplify common types
            ann_str = ann_str.replace("typing.", "").replace("<class '", "").replace("'>", "")
            if "Dict" in ann_str:
                ann_str = "dict"
            elif "List" in ann_str:
                ann_str = "list"
            elif "Optional" in ann_str:
                ann_str = ann_str.split("[")[-1].split("]")[0] + " | None"
            param_str += f": {ann_str}"
        if param.default != inspect.Parameter.empty:
            default_repr = repr(param.default)
            param_str += f" = {default_repr}"
        params.append(param_str)
    
    params_str = ", ".join(params)
    
    # Generate stub code
    stub_code = f'''"""Generated stub for {tool_name} tool.

{docstring}

This stub allows the tool to be used in code execution via filesystem discovery,
following Anthropic's code execution with MCP pattern.
Reference: https://www.anthropic.com/engineering/code-execution-with-mcp
"""

from typing import Any, Dict

# Import MCP client (will be available in execution context)
try:
    from {import_path} import MCPClient
    {client_var} = MCPClient.get_instance()
except ImportError:
    # Fallback: tool will be called directly if client not available
    {client_var} = None


async def {tool_name}({params_str}) -> Dict[str, Any]:
    """{docstring}
    
    This is a stub that calls the actual MCP tool.
    The tool can be discovered via filesystem and used in code execution.
    """
    if {client_var} is None:
        raise RuntimeError("MCP client not available in execution context")
    
    # Call the tool via MCP client
    result = await {client_var}.call_tool_mcp("{tool_name}", {{
'''
    
    # Add parameters to the call
    for param_name in sig.parameters:
        if param_name != "self":
            stub_code += f'        "{param_name}": {param_name},\n'
    
    stub_code += '''    }})
    
    # Extract text content if present
    if hasattr(result, "content") and result.content:
        import json
        return json.loads(result.content[0].text)
    
    return result
'''
    
    return stub_code


def generate_server_index(server_name: str, tool_names: List[str]) -> str:
    """Generate an index.py file for a server directory.
    
    Creates an index file that exports all tools, following the pattern:
    import * as server from './servers/server-name'
    
    Args:
        server_name: Name of the server
        tool_names: List of tool names in the server
        
    Returns:
        Python code as a string for the index file
    """
    imports = []
    exports = []
    
    for tool_name in tool_names:
        # Convert tool name to valid Python identifier
        safe_name = tool_name.replace("-", "_").replace(".", "_")
        imports.append(f"from .{tool_name} import {tool_name} as {safe_name}")
        exports.append(safe_name)
    
    index_code = f'''"""Index file for {server_name} server.

This file exports all tools from the {server_name} server,
allowing imports like: import * as {server_name} from './servers/{server_name}'
"""

{chr(10).join(imports)}

__all__ = {exports}
'''
    
    return index_code


def create_filesystem_stubs(
    tools: List[Callable],
    server_name: str,
    servers_dir: Path,
    import_path: str = "code_execution_mcp.client.mcp_client",
) -> None:
    """Create filesystem stubs for a list of tools.
    
    This function creates a server directory and generates stub files for each tool,
    making them discoverable via filesystem following Anthropic's pattern.
    
    Args:
        tools: List of tool functions to create stubs for
        server_name: Name of the server (directory name)
        servers_dir: Path to the servers directory
        import_path: Path to import the MCP client from
        
    Example:
        # Create stubs for context tools
        create_filesystem_stubs(
            context_tools,
            server_name="context",
            servers_dir=Path("./servers")
        )
        # Creates: servers/context/get_context_metadata.py, etc.
    """
    server_dir = servers_dir / server_name
    server_dir.mkdir(parents=True, exist_ok=True)
    
    tool_names = []
    
    for tool_func in tools:
        tool_name = tool_func.__name__
        tool_names.append(tool_name)
        
        # Generate stub
        stub_code = generate_tool_stub(
            tool_func,
            server_name=server_name,
            tool_name=tool_name,
            import_path=import_path,
        )
        
        # Write stub file
        stub_file = server_dir / f"{tool_name}.py"
        stub_file.write_text(stub_code)
        logger.info(f"Created stub: {stub_file}")
    
    # Create index file
    index_code = generate_server_index(server_name, tool_names)
    index_file = server_dir / "__init__.py"
    index_file.write_text(index_code)
    logger.info(f"Created index: {index_file}")


def create_context_tools_stubs(
    servers_dir: Path,
    import_path: str = "code_execution_mcp.client.mcp_client",
) -> None:
    """Create filesystem stubs for context tools.
    
    Args:
        servers_dir: Path to the servers directory
        import_path: Path to import the MCP client from
    """
    try:
        from code_execution_mcp.context_tools import create_context_tools
        import sys
        from pathlib import Path
        
        # Get orchestrator (assuming backend path structure)
        backend_path = Path(__file__).parent.parent.parent / "Mach" / "backend"
        if backend_path.exists():
            sys.path.insert(0, str(backend_path))
            from agent import orchestrator
            
            context_tools = create_context_tools(orchestrator)
            create_filesystem_stubs(
                context_tools,
                server_name="context",
                servers_dir=servers_dir,
                import_path=import_path,
            )
        else:
            logger.warning(f"Backend path not found: {backend_path}")
    except ImportError as e:
        logger.warning(f"Could not create context tools stubs: {e}")


def create_external_tools_stubs(
    server_name: str,
    tool_names: List[str],
    servers_dir: Path,
    import_path: str = "code_execution_mcp.client.mcp_client",
) -> None:
    """Create filesystem stubs for external tools.
    
    Args:
        server_name: Name of the external server
        tool_names: List of tool names from the external server
        servers_dir: Path to the servers directory
        import_path: Path to import the MCP client from
    """
    server_dir = servers_dir / server_name
    server_dir.mkdir(parents=True, exist_ok=True)
    
    # Create stub files for each tool
    for tool_name in tool_names:
        # Generate a generic stub (we don't have the actual function)
        stub_code = f'''"""Generated stub for {tool_name} tool from external server {server_name}.

This stub allows the external tool to be used in code execution via filesystem discovery.
"""

from typing import Any, Dict

try:
    from {import_path} import MCPClient
    mcp_client = MCPClient.get_instance()
except ImportError:
    mcp_client = None


async def {tool_name}(**kwargs) -> Dict[str, Any]:
    """Call {tool_name} tool from external server {server_name}."""
    if mcp_client is None:
        raise RuntimeError("MCP client not available in execution context")
    
    result = await mcp_client.call_tool_mcp("{tool_name}", kwargs)
    
    if hasattr(result, "content") and result.content:
        import json
        return json.loads(result.content[0].text)
    
    return result
'''
        
        stub_file = server_dir / f"{tool_name}.py"
        stub_file.write_text(stub_code)
        logger.info(f"Created external tool stub: {stub_file}")
    
    # Create index file
    index_code = generate_server_index(server_name, tool_names)
    index_file = server_dir / "__init__.py"
    index_file.write_text(index_code)
    logger.info(f"Created external server index: {index_file}")

