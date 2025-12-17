"""Context-aware tools for Code Execution MCP framework.

This module provides context-aware tools that can be integrated into the
code-execution-mcp framework. These tools allow accessing session context
via JWT tokens.
"""

import json
from typing import Any, Dict, List, Optional

try:
    from fastmcp.server.dependencies import get_http_request
    from starlette.requests import Request as MCPRequest
    from fastapi import HTTPException
except ImportError:
    # Fallback if not using FastMCP HTTP transport
    get_http_request = None
    MCPRequest = None
    HTTPException = None


def create_context_tools(
    orchestrator_module: Any,
    context_manager_module: Any = None,
) -> List[callable]:
    """Create context-aware tools for integration into code-execution-mcp.

    Args:
        orchestrator_module: Module containing orchestrator functions
            (must have `extract_token` and `get_session` functions)
        context_manager_module: Optional context manager module (for type hints)

    Returns:
        List of tool functions that can be registered with MCPServer

    Example:
        from agentkernel import create_server
        from agentkernel.context_tools import create_context_tools
        import sys
        sys.path.insert(0, '/path/to/backend')
        from agent import orchestrator

        # Create context tools
        context_tools = create_context_tools(orchestrator)

        # Create server with context tools
        server = create_server(custom_tools=context_tools)
    """
    if get_http_request is None:
        raise ImportError(
            "fastmcp is required for context tools. Install with: pip install fastmcp"
        )

    tools = []

    async def _get_context_from_request(request: MCPRequest) -> Optional[object]:
        """Extract JWT token from request and return the session context."""
        authorization = request.headers.get("Authorization")
        jwt_token = orchestrator_module.extract_token(request, authorization)

        if not jwt_token:
            raise HTTPException(
                status_code=401,
                detail="Missing JWT token. Provide Authorization: Bearer <JWT> header.",
            )

        context = await orchestrator_module.get_session(jwt_token)
        if not context:
            raise HTTPException(status_code=404, detail="Session not found or token invalid")

        return context

    async def get_context_metadata() -> Dict[str, Any]:
        """Get context metadata including session ID, user ID, model ID, and creation timestamp."""
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        authorization = request.headers.get("Authorization")
        jwt_token = orchestrator_module.extract_token(request, authorization)
        jwt_payload = (
            orchestrator_module.get_jwt_token_payload(jwt_token)
            if jwt_token and hasattr(orchestrator_module, "get_jwt_token_payload")
            else None
        )

        return {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "model_id": context.model_id,
            "client_id": context.client_id,
            "token": context.token,
            "created_at": context.created_at,
            "jwt_payload": jwt_payload,
        }

    async def get_conversation_history() -> Dict[str, Any]:
        """Get the conversation history from the current session context. Returns all messages in the conversation."""
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        # Get messages from context
        messages = await context.get_messages()

        return {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "model_id": context.model_id,
            "client_id": context.client_id,
            "message_count": len(messages),
            "messages": messages,
            "created_at": context.created_at,
        }

    async def get_session_info() -> Dict[str, Any]:
        """Get summary information about the current session context including metadata and statistics."""
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        messages = await context.get_messages()

        # Count messages by role
        role_counts = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1

        # Count tool calls
        tool_call_count = len(context.tool_calls)

        return {
            "session_id": context.session_id,
            "user_id": context.user_id,
            "model_id": context.model_id,
            "client_id": context.client_id,
            "created_at": context.created_at,
            "statistics": {
                "total_messages": len(messages),
                "messages_by_role": role_counts,
                "total_tool_calls": tool_call_count,
                "total_message_history": len(context.message_history),
            },
        }

    async def search_conversation(
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Search through the conversation history for messages containing specific keywords or matching a role.

        Args:
            keyword: Optional keyword to search for in message content
            role: Optional role filter (e.g., 'user', 'assistant', 'tool')
            limit: Maximum number of results to return (default: 10)
        """
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        messages = await context.get_messages()

        # Filter messages
        filtered = []
        for msg in messages:
            # Filter by role if specified
            if role and msg.get("role") != role:
                continue

            # Filter by keyword if specified
            if keyword:
                content = msg.get("content", "")
                if keyword.lower() not in content.lower():
                    continue

            filtered.append(msg)
            if len(filtered) >= limit:
                break

        return {
            "query": {
                "keyword": keyword,
                "role": role,
                "limit": limit,
            },
            "results_count": len(filtered),
            "results": filtered,
        }

    async def get_tool_calls(
        endpoint: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all tool calls made in this session, optionally filtered by endpoint or tool name.

        Args:
            endpoint: Optional filter by endpoint name
            tool_name: Optional filter by tool name
        """
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        tool_calls = context.tool_calls

        # Apply filters
        if endpoint or tool_name:
            filtered = []
            for tc in tool_calls:
                if endpoint and tc.get("endpoint") != endpoint:
                    continue
                if tool_name and tc.get("name") != tool_name:
                    continue
                filtered.append(tc)
            tool_calls = filtered

        return {
            "total_tool_calls": len(tool_calls),
            "filters": {
                "endpoint": endpoint,
                "tool_name": tool_name,
            },
            "tool_calls": tool_calls,
        }

    async def get_recent_messages(count: int = 5) -> Dict[str, Any]:
        """Get the latest N messages from the conversation, useful for getting recent context.

        Args:
            count: Number of recent messages to retrieve (default: 5)
        """
        request: MCPRequest = get_http_request()
        context = await _get_context_from_request(request)

        messages = await context.get_messages()

        # Get the last N messages
        recent = messages[-count:] if len(messages) > count else messages

        return {
            "requested_count": count,
            "returned_count": len(recent),
            "messages": recent,
        }

    # Return list of tool functions
    return [
        get_context_metadata,
        get_conversation_history,
        get_session_info,
        search_conversation,
        get_tool_calls,
        get_recent_messages,
    ]
