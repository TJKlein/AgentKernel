import pytest
import os
from client.agent_helper import AgentHelper
from client.monty_executor import MontyExecutor
from client.filesystem_helpers import FilesystemHelper
from client.base import ExecutionResult

# Skip if Monty or keys missing
try:
    import pydantic_monty
    HAS_MONTY = True
except ImportError:
    HAS_MONTY = False

@pytest.mark.live
@pytest.mark.skipif(not HAS_MONTY, reason="Monty backend required")
class TestVanillaMontyLive:
    
    @pytest.fixture
    def agent_helper(self, mock_config, temp_workspace, temp_servers, live_llm_client):
        """Create a standard AgentHelper with real Monty and Live Client."""
        fs_helper = FilesystemHelper(
            workspace_dir=str(temp_workspace),
            servers_dir=str(temp_servers),
            skills_dir="./skills"
        )
        
        executor = MontyExecutor(
            execution_config=mock_config.execution
        )
        
        helper = AgentHelper(
            fs_helper=fs_helper,
            executor=executor,
            llm_config=mock_config.llm
        )
        
        # Inject live client
        helper.code_generator._llm_client = live_llm_client
        helper.code_generator._model_name = "gpt-4o"
        
        return helper

    def test_live_vanilla_calculation(self, agent_helper):
        """Verify standard agent can do math using Monty and Real LLM."""
        task = "Calculate the square root of 144 and multiply by 10"
        
        print("\n[Live] Executing Vanilla Monty task...")
        status, output, error = agent_helper.execute_task(task)
        
        assert error is None
        assert status == ExecutionResult.SUCCESS
        assert "120" in str(output)
