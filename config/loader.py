"""Configuration loading and validation."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from config.schema import AppConfig, MCPServerConfig, WorkflowConfig


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config: Dict[str, Any] = {
        "mcp_servers": [],
        "guardrails": {},
        "execution": {},
        "logging": {},
    }

    # Load MCP servers from environment
    server_prefix = "MCP_SERVER_"
    server_names = set()
    for key in os.environ:
        if key.startswith(server_prefix) and key.endswith("_URL"):
            server_name = key[len(server_prefix) : -4].lower()
            server_names.add(server_name)

    for server_name in server_names:
        url_key = f"{server_prefix}{server_name.upper()}_URL"
        url = os.environ.get(url_key)
        if url:
            config["mcp_servers"].append({"name": server_name, "url": url})

    # Load guardrails config
    if os.environ.get("GUARDRAILS_ENABLED", "true").lower() == "true":
        config["guardrails"] = {
            "enabled": True,
            "strict_mode": os.environ.get("GUARDRAILS_STRICT_MODE", "false").lower() == "true",
        }

    # Load execution config
    config["execution"] = {
        "workspace_dir": os.environ.get("WORKSPACE_DIR", "./workspace"),
        "servers_dir": os.environ.get("SERVERS_DIR", "./servers"),
        "skills_dir": os.environ.get("SKILLS_DIR", "./skills"),
        "allow_network_access": os.environ.get("ALLOW_NETWORK_ACCESS", "false").lower() == "true",
    }

    # Load logging config
    config["logging"] = {
        "level": os.environ.get("LOG_LEVEL", "INFO"),
        "file": os.environ.get("LOG_FILE", "logs/code-execution-mcp.log"),
    }

    return config


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load and validate configuration."""
    if config_path and Path(config_path).exists():
        config_dict = load_config_from_file(config_path)
    else:
        config_dict = load_config_from_env()

    # Merge with environment overrides
    env_config = load_config_from_env()
    if env_config.get("mcp_servers"):
        config_dict.setdefault("mcp_servers", []).extend(env_config["mcp_servers"])

    return AppConfig(**config_dict)


class ConfigLoader:
    """Configuration loader with caching."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the config loader."""
        self.config_path = config_path
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """Load configuration (cached)."""
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config

    def reload(self) -> AppConfig:
        """Reload configuration."""
        self._config = load_config(self.config_path)
        return self._config

    def get_mcp_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """Get configuration for a specific MCP server."""
        config = self.load()
        for server_config in config.mcp_servers:
            if server_config.name == server_name:
                return server_config
        return None

    def get_workflow_config(self, workflow_name: str) -> Optional[WorkflowConfig]:
        """Get configuration for a specific workflow."""
        config = self.load()
        for workflow_config in config.workflows:
            if workflow_config.name == workflow_name:
                return workflow_config
        return None
