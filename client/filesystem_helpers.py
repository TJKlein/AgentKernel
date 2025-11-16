"""Filesystem utilities for state persistence and tool discovery."""

import json
import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
from functools import lru_cache

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class FilesystemHelper:
    """Helper class for filesystem operations."""

    def _find_project_root(self) -> Path:
        """Find project root by looking for marker files (pyproject.toml, requirements.txt, etc.)."""
        current = Path.cwd().resolve()
        
        # Check current directory and parents
        for path in [current] + list(current.parents):
            # Look for project markers
            markers = ["pyproject.toml", "requirements.txt", ".git", "setup.py"]
            if any((path / marker).exists() for marker in markers):
                # Also verify client directory exists (confirms it's the right root)
                if (path / "client").exists():
                    return path
        
        # Fallback: assume current directory is project root if client exists
        if (current / "client").exists():
            return current
        
        # Last resort: use current directory
        logger.warning(f"Could not find project root, using current directory: {current}")
        return current

    def __init__(self, workspace_dir: str, servers_dir: str, skills_dir: str):
        """Initialize filesystem helper."""
        # Find project root first (works regardless of current working directory)
        project_root = self._find_project_root()
        logger.debug(f"Project root: {project_root}")
        
        # Resolve all paths relative to project root
        self.workspace_dir = (project_root / workspace_dir.lstrip("./")).resolve()
        self.servers_dir = (project_root / servers_dir.lstrip("./")).resolve()
        self.skills_dir = (project_root / skills_dir.lstrip("./")).resolve()

        # Create directories if they don't exist
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.servers_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for tool discovery (server/tool lists)
        self._servers_cache: Optional[List[str]] = None
        self._servers_cache_mtime: Optional[float] = None
        self._tools_cache: Dict[str, List[str]] = {}
        self._tools_cache_mtime: Dict[str, float] = {}

    def list_servers(self) -> List[str]:
        """List available MCP servers in the servers directory.
        
        Optimized using os.scandir() and caching for sub-100ms performance.
        """
        servers_path = str(self.servers_dir)
        
        # Check cache validity using directory mtime
        if os.path.exists(servers_path):
            try:
                current_mtime = os.path.getmtime(servers_path)
                if (self._servers_cache is not None and 
                    self._servers_cache_mtime == current_mtime):
                    return self._servers_cache
            except OSError:
                pass
        
        # Scan directory
        servers = []
        if os.path.exists(servers_path):
            try:
                # Use os.scandir() - much faster than Path.iterdir()
                with os.scandir(servers_path) as entries:
                    for entry in entries:
                        if entry.is_dir() and not entry.name.startswith("__"):
                            servers.append(entry.name)
            except (OSError, PermissionError) as e:
                logger.warning(f"Error scanning servers directory: {e}")
        
        servers = sorted(servers)
        
        # Update cache
        if os.path.exists(servers_path):
            try:
                self._servers_cache = servers
                self._servers_cache_mtime = os.path.getmtime(servers_path)
            except OSError:
                pass
        
        return servers

    def list_tools(self, server_name: str) -> List[str]:
        """List available tools for a server.
        
        Optimized using os.scandir() and caching for sub-100ms performance.
        """
        server_path = str(self.servers_dir / server_name)
        
        # Check cache validity using directory mtime
        if os.path.exists(server_path):
            try:
                current_mtime = os.path.getmtime(server_path)
                if (server_name in self._tools_cache and 
                    self._tools_cache_mtime.get(server_name) == current_mtime):
                    return self._tools_cache[server_name]
            except OSError:
                pass
        
        # Scan directory
        tools = []
        if os.path.exists(server_path):
            try:
                # Use os.scandir() - much faster than Path.iterdir()
                with os.scandir(server_path) as entries:
                    for entry in entries:
                        if entry.is_file() and entry.name.endswith(".py") and not entry.name.startswith("__"):
                            # Remove .py extension
                            tools.append(entry.name[:-3])
            except (OSError, PermissionError) as e:
                logger.warning(f"Error scanning tools directory for {server_name}: {e}")
        
        tools = sorted(tools)
        
        # Update cache
        if os.path.exists(server_path):
            try:
                self._tools_cache[server_name] = tools
                self._tools_cache_mtime[server_name] = os.path.getmtime(server_path)
            except OSError:
                pass
        
        return tools

    def read_tool_file(self, server_name: str, tool_name: str) -> Optional[str]:
        """Read a tool file."""
        tool_path = self.servers_dir / server_name / f"{tool_name}.py"
        if tool_path.exists():
            return tool_path.read_text(encoding="utf-8")
        return None

    def read_skill(self, skill_name: str) -> Optional[str]:
        """Read a skill file."""
        skill_path = self.skills_dir / f"{skill_name}.py"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return None

    def save_skill(self, skill_name: str, code: str, description: Optional[str] = None) -> Path:
        """Save a skill to the skills directory."""
        skill_path = self.skills_dir / f"{skill_name}.py"
        skill_path.write_text(code, encoding="utf-8")

        # Save description if provided
        if description:
            desc_path = self.skills_dir / f"{skill_name}.md"
            desc_path.write_text(description, encoding="utf-8")

        logger.info(f"Saved skill: {skill_name}")
        return skill_path

    def save_json(self, filename: str, data: Any, validate: Optional[BaseModel] = None) -> Path:
        """Save data as JSON file."""
        file_path = self.workspace_dir / filename

        # Validate if model provided
        if validate:
            try:
                if isinstance(data, dict):
                    validate(**data)
                else:
                    validate(data)
            except ValidationError as e:
                raise ValueError(f"Validation failed: {e}")

        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Saved JSON: {filename}")
        return file_path

    def load_json(self, filename: str, validate: Optional[BaseModel] = None) -> Any:
        """Load data from JSON file."""
        file_path = self.workspace_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        data = json.loads(file_path.read_text(encoding="utf-8"))

        # Validate if model provided
        if validate:
            try:
                if isinstance(data, dict):
                    return validate(**data)
                else:
                    return validate(data)
            except ValidationError as e:
                raise ValueError(f"Validation failed: {e}")

        return data

    def save_csv(self, filename: str, data: List[Dict[str, Any]]) -> Path:
        """Save data as CSV file."""
        file_path = self.workspace_dir / filename

        if not data:
            file_path.write_text("", encoding="utf-8")
            return file_path

        fieldnames = list(data[0].keys())
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        logger.info(f"Saved CSV: {filename}")
        return file_path

    def load_csv(self, filename: str) -> List[Dict[str, Any]]:
        """Load data from CSV file."""
        file_path = self.workspace_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def save_text(self, filename: str, content: str) -> Path:
        """Save text content to file."""
        file_path = self.workspace_dir / filename
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Saved text: {filename}")
        return file_path

    def load_text(self, filename: str) -> str:
        """Load text content from file."""
        file_path = self.workspace_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        return file_path.read_text(encoding="utf-8")

    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in workspace."""
        return (self.workspace_dir / filename).exists()

    def delete_file(self, filename: str) -> None:
        """Delete a file from workspace."""
        file_path = self.workspace_dir / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {filename}")

    def list_workspace_files(self) -> List[str]:
        """List all files in workspace."""
        files = []
        if self.workspace_dir.exists():
            for item in self.workspace_dir.iterdir():
                if item.is_file():
                    files.append(item.name)
        return sorted(files)
