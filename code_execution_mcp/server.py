#!/usr/bin/env python3
"""Entry point for running the Code Execution MCP framework as an MCP server.

Usage:
    python -m code_execution_mcp.server [stdio|sse|http]
    
Or:
    code-execution-mcp-server [stdio|sse|http]
"""

import sys


def main():
    """Main entry point for the MCP server."""
    from server.mcp_server import run_server
    
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_server(transport=transport)


if __name__ == "__main__":
    main()

