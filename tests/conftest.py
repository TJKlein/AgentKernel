import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.schema import AppConfig, LLMConfig, ExecutionConfig, OptimizationConfig, GuardrailConfig

@pytest.fixture
def mock_llm_client():
    """Mock OpenAI client to avoid API calls."""
    mock = MagicMock()
    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Mocked LLM response"))
    ]
    mock.chat.completions.create.return_value = mock_response
    return mock

@pytest.fixture
def mock_config():
    """Provides a standard test configuration."""
    return AppConfig(
        llm=LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key",
            enabled=True,
            temperature=0.0
        ),
        execution=ExecutionConfig(
            sandbox_type="monty", # Default for unit tests (faster)
            timeout=30
        ),
        optimizations=OptimizationConfig(
            enabled=True
        ),
        guardrails=GuardrailConfig(
            enabled=False
        )
    )

@pytest.fixture
def temp_workspace(tmp_path):
    """Provides a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace

@pytest.fixture
def temp_servers(tmp_path):
    """Provides a temporary servers directory."""
    servers = tmp_path / "servers"
    servers.mkdir()
    return servers

@pytest.fixture
def live_llm_client():
    """Provides a real OpenAI client if API key is present."""
    # Load .env file if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        pytest.skip("No API key found. Skipping live test.")
    
    try:
        from openai import OpenAI, AzureOpenAI
        if os.environ.get("AZURE_OPENAI_API_KEY"):
            return AzureOpenAI(
                api_key=api_key,
                api_version="2023-05-15",
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "")
            )
        else:
            return OpenAI(api_key=api_key)
    except ImportError:
        pytest.skip("openai package not installed.")
