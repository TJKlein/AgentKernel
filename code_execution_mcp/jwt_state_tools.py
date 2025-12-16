"""JWT-aware state management tools for Code Execution MCP framework.

This module provides state management tools that are scoped per user/session
using JWT tokens, ensuring each user's state is isolated.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from fastmcp.server.dependencies import get_http_request
    from starlette.requests import Request as MCPRequest
    from fastapi import HTTPException
except ImportError:
    get_http_request = None
    MCPRequest = None
    HTTPException = None

logger = logging.getLogger(__name__)


def create_jwt_state_tools(
    orchestrator_module: Any,
    base_workspace_dir: str = "./workspace",
) -> list:
    """Create JWT-aware state management tools.
    
    These tools automatically scope state files per user using JWT tokens,
    ensuring:
    - Each user's state is isolated from other users
    - The same user can continue their session across different sessions
    - State persistence is based on user_id (from JWT "sub" claim)
    
    Args:
        orchestrator_module: Module containing orchestrator functions
            (must have `extract_token` and `get_jwt_token_payload` functions)
        base_workspace_dir: Base directory for workspace (user-specific dirs created inside)
    
    Returns:
        List of tool functions: [get_state, save_state]
        
    Example:
        from code_execution_mcp import create_server
        from code_execution_mcp.jwt_state_tools import create_jwt_state_tools
        from agent import orchestrator
        
        server = create_server()
        
        # Replace default state tools with JWT-aware versions
        jwt_state_tools = create_jwt_state_tools(orchestrator)
        for tool in jwt_state_tools:
            server.register_tool(tool)
    """
    if get_http_request is None:
        raise ImportError(
            "fastmcp is required for JWT state tools. Install with: pip install fastmcp"
        )
    
    base_workspace = Path(base_workspace_dir)
    
    def _get_user_workspace() -> Path:
        """Get user-specific workspace directory from JWT token."""
        request: MCPRequest = get_http_request()
        authorization = request.headers.get("Authorization")
        jwt_token = orchestrator_module.extract_token(request, authorization)
        
        if not jwt_token:
            raise HTTPException(
                status_code=401,
                detail="Missing JWT token. Provide Authorization: Bearer <JWT> header.",
            )
        
        # Get user/session info from JWT
        jwt_payload = orchestrator_module.get_jwt_token_payload(jwt_token)
        if not jwt_payload:
            raise HTTPException(
                status_code=401,
                detail="Invalid JWT token.",
            )
        
        # Use user_id as primary identifier for workspace isolation
        # This ensures the same user can continue their session across different sessions
        # JWT payload uses "sub" field for user_id (standard JWT claim)
        user_id = jwt_payload.get("sub") or jwt_payload.get("user_id") or jwt_payload.get("session_id")
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="JWT token missing user identifier (sub/user_id).",
            )
        
        # Create user-specific workspace directory
        # Same user_id = same workspace = can continue session across different sessions
        # Different user_id = different workspace = complete isolation
        user_workspace = base_workspace / f"users/{user_id}"
        user_workspace.mkdir(parents=True, exist_ok=True)
        
        return user_workspace
    
    def get_state(state_file: str = "state.json") -> Dict[str, Any]:
        """Get the current state from the user's workspace (JWT-scoped).
        
        State is automatically scoped to the user_id identified by the JWT token.
        This ensures:
        - The same user can continue their session across different sessions
        - Different users cannot access each other's state
        - State persistence is based on user_id (from JWT "sub" claim)
        
        Args:
            state_file: Name of the state file to read (default: "state.json")
        
        Returns:
            Dictionary containing the state data
        """
        try:
            user_workspace = _get_user_workspace()
            
            state_path = user_workspace / state_file
            if not state_path.exists():
                return {
                    "exists": False,
                    "data": {},
                    "workspace": str(user_workspace),
                }
            
            with open(state_path, "r") as f:
                data = json.load(f)
            
            return {
                "exists": True,
                "data": data,
                "workspace": str(user_workspace),
                "file": str(state_path),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error reading state: {e}", exc_info=True)
            return {"exists": False, "error": str(e), "data": {}}
    
    def save_state(
        state_data: Dict[str, Any],
        state_file: str = "state.json",
    ) -> Dict[str, Any]:
        """Save state to the user's workspace (JWT-scoped).
        
        State is automatically scoped to the user_id identified by the JWT token.
        This ensures:
        - The same user can continue their session across different sessions
        - Different users cannot access each other's state
        - State persistence is based on user_id (from JWT "sub" claim)
        
        Args:
            state_data: Dictionary containing state data to save
            state_file: Name of the state file to write (default: "state.json")
        
        Returns:
            Dictionary with success status and file path
        """
        try:
            user_workspace = _get_user_workspace()
            
            state_path = user_workspace / state_file
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(state_path, "w") as f:
                json.dump(state_data, f, indent=2)
            
            return {
                "success": True,
                "file": str(state_path),
                "workspace": str(user_workspace),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error saving state: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    # Set docstrings
    get_state.__doc__ = """Get the current state from the user's workspace (JWT-scoped).
    
    State is automatically scoped to the user_id identified by the JWT token.
    This ensures the same user can continue their session across different sessions,
    while different users are completely isolated from each other.
    """
    
    save_state.__doc__ = """Save state to the user's workspace (JWT-scoped).
    
    State is automatically scoped to the user_id identified by the JWT token.
    This ensures the same user can continue their session across different sessions,
    while different users are completely isolated from each other.
    """
    
    return [get_state, save_state]

