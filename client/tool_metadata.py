"""Tool metadata extraction for progressive disclosure.

This module provides efficient ways to extract tool metadata without loading
all tool definitions, enabling progressive disclosure in search_tools.
"""

import ast
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)


def extract_tool_description_from_file(file_path: Path) -> Optional[str]:
    """Extract tool description from a Python file without loading it.
    
    This is faster than reading the full file and parsing it.
    
    Args:
        file_path: Path to the tool file
        
    Returns:
        Tool description (docstring) or None
    """
    try:
        # Read only first few KB (enough for docstring)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(8192)  # Read first 8KB
        
        # Parse AST to extract docstring
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                if docstring:
                    return docstring
    except Exception as e:
        logger.debug(f"Failed to extract description from {file_path}: {e}")
    return None


def extract_tool_metadata_from_file(file_path: Path) -> Dict[str, str]:
    """Extract tool metadata (name, description) from a file.
    
    Args:
        file_path: Path to the tool file
        
    Returns:
        Dict with 'name', 'description', 'server' keys
    """
    tool_name = file_path.stem
    description = extract_tool_description_from_file(file_path) or ""
    
    return {
        "name": tool_name,
        "description": description,
        "server": file_path.parent.name,
    }


class ToolMetadataIndex:
    """Lightweight index of tool metadata for progressive disclosure."""
    
    def __init__(self, servers_dir: Path):
        """Initialize metadata index.
        
        Args:
            servers_dir: Path to servers directory
        """
        self.servers_dir = Path(servers_dir)
        self._metadata_cache: Dict[Tuple[str, str], Dict[str, str]] = {}
        self._cache_mtime: Dict[str, float] = {}
    
    def get_tool_metadata(self, server_name: str, tool_name: str) -> Optional[Dict[str, str]]:
        """Get metadata for a specific tool.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            
        Returns:
            Tool metadata dict or None
        """
        cache_key = (server_name, tool_name)
        
        # Check cache
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]
        
        # Extract from file
        tool_path = self.servers_dir / server_name / f"{tool_name}.py"
        if tool_path.exists():
            metadata = extract_tool_metadata_from_file(tool_path)
            self._metadata_cache[cache_key] = metadata
            return metadata
        
        return None
    
    def get_all_tool_metadata(self, server_name: Optional[str] = None) -> Dict[Tuple[str, str], Dict[str, str]]:
        """Get metadata for all tools (or tools in a specific server).
        
        This is still efficient because we only read docstrings, not full files.
        
        Args:
            server_name: Optional server name to filter by
            
        Returns:
            Dict mapping (server_name, tool_name) to metadata
        """
        metadata = {}
        servers_to_scan = [server_name] if server_name else self._list_servers()
        
        for srv_name in servers_to_scan:
            server_path = self.servers_dir / srv_name
            if not server_path.exists():
                continue
            
            # Check cache validity
            try:
                current_mtime = os.path.getmtime(str(server_path))
                if self._cache_mtime.get(srv_name) == current_mtime:
                    # Use cached metadata for this server
                    for key, value in self._metadata_cache.items():
                        if key[0] == srv_name:
                            metadata[key] = value
                    continue
                
                self._cache_mtime[srv_name] = current_mtime
            except OSError:
                pass
            
            # Extract metadata from files
            try:
                for tool_file in server_path.glob("*.py"):
                    if tool_file.name.startswith("__"):
                        continue
                    
                    tool_name = tool_file.stem
                    cache_key = (srv_name, tool_name)
                    
                    if cache_key not in self._metadata_cache:
                        tool_meta = extract_tool_metadata_from_file(tool_file)
                        self._metadata_cache[cache_key] = tool_meta
                    
                    metadata[cache_key] = self._metadata_cache[cache_key]
            except Exception as e:
                logger.warning(f"Error scanning server {srv_name}: {e}")
        
        return metadata
    
    def _list_servers(self) -> List[str]:
        """List all server directories."""
        if not self.servers_dir.exists():
            return []
        
        servers = []
        try:
            for entry in os.scandir(str(self.servers_dir)):
                if entry.is_dir() and not entry.name.startswith("__"):
                    servers.append(entry.name)
        except (OSError, PermissionError) as e:
            logger.warning(f"Error listing servers: {e}")
        
        return sorted(servers)
    
    def search_tool_names(self, query: str, max_results: int = 10) -> Dict[str, List[str]]:
        """Search tool names using simple keyword matching (fast, no semantic search).
        
        This is the fastest search method - only searches filenames and basic keywords.
        
        Args:
            query: Search query
            max_results: Maximum results per server
            
        Returns:
            Dict mapping server names to lists of matching tool names
        """
        query_lower = query.lower()
        query_words = query_lower.split()
        
        results: Dict[str, List[str]] = {}
        servers = self._list_servers()
        
        for server_name in servers:
            server_path = self.servers_dir / server_name
            if not server_path.exists():
                continue
            
            matching_tools = []
            try:
                for tool_file in server_path.glob("*.py"):
                    if tool_file.name.startswith("__"):
                        continue
                    
                    tool_name = tool_file.stem
                    tool_name_lower = tool_name.lower()
                    
                    # Simple keyword matching
                    if any(word in tool_name_lower for word in query_words):
                        matching_tools.append(tool_name)
                    
                    if len(matching_tools) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Error searching tools in {server_name}: {e}")
            
            if matching_tools:
                results[server_name] = matching_tools
        
        return results

