import pytest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Load .env from project root so test and live LLM config match production loader.
try:
    from dotenv import load_dotenv
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass

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
def live_app_config():
    """Load app config from .env / config loader (same as production)."""
    from config.loader import load_config
    return load_config()


@pytest.fixture
def live_llm_client(live_app_config):
    """Return a live OpenAI or Azure client from config loaded from .env. Fails if API key is not set."""
    llm = live_app_config.llm
    api_key = llm.api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        pytest.fail("API key required. Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in .env")

    try:
        from openai import OpenAI, AzureOpenAI
        if llm.provider == "azure_openai" and llm.azure_endpoint:
            return AzureOpenAI(
                api_key=api_key,
                api_version=llm.azure_api_version,
                azure_endpoint=llm.azure_endpoint.rstrip("/"),
            )
        return OpenAI(api_key=api_key)
    except ImportError as e:
        pytest.fail(f"openai package not installed: {e}")


@pytest.fixture
def live_llm_model_name(live_app_config):
    """Model or deployment name from config. For Azure, use a chat-capable deployment when the configured one does not support chat completions."""
    llm = live_app_config.llm
    if llm.provider == "azure_openai":
        name = (llm.azure_deployment_name or "").strip()
        # Use a chat-capable deployment when the configured one does not support chat completions.
        if not name or "codex" in name.lower():
            return os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5.2-chat")
        return name
    return llm.model or "gpt-4o"


