"""Filesystem utilities for state persistence and tool discovery."""

import json
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class FilesystemHelper:
    """Helper class for filesystem operations."""

    def __init__(self, workspace_dir: str, servers_dir: str, skills_dir: str):
        """Initialize filesystem helper."""
        self.workspace_dir = Path(workspace_dir)
        self.servers_dir = Path(servers_dir)
        self.skills_dir = Path(skills_dir)

        # Create directories if they don't exist
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.servers_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_servers(self) -> List[str]:
        """List available MCP servers in the servers directory."""
        servers = []
        if self.servers_dir.exists():
            for item in self.servers_dir.iterdir():
                if item.is_dir() and not item.name.startswith("__"):
                    servers.append(item.name)
        return sorted(servers)

    def list_tools(self, server_name: str) -> List[str]:
        """List available tools for a server."""
        server_dir = self.servers_dir / server_name
        tools = []
        if server_dir.exists():
            for item in server_dir.iterdir():
                if item.is_file() and item.suffix == ".py" and not item.name.startswith("__"):
                    tools.append(item.stem)
        return sorted(tools)

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
