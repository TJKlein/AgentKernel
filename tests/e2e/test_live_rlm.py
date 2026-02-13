import pytest
from client.recursive_agent import RecursiveAgent
from client.monty_executor import MontyExecutor
from client.filesystem_helpers import FilesystemHelper
from client.base import ExecutionResult

# Skip if Monty not installed
try:
    import pydantic_monty
    HAS_MONTY = True
except ImportError:
    HAS_MONTY = False

@pytest.mark.live
@pytest.mark.skipif(not HAS_MONTY, reason="Monty backend required")
class TestRecursiveAgentLive:
    
    @pytest.fixture
    def agent(self, mock_config, temp_workspace, temp_servers, live_llm_client):
        """Create a RecursiveAgent instance with real Monty executor and real LLM."""
        # Setup filesystem helper
        fs_helper = FilesystemHelper(
            workspace_dir=str(temp_workspace),
            servers_dir=str(temp_servers),
            skills_dir="./skills",
        )
        
        # Setup Monty executor
        executor = MontyExecutor(
            execution_config=mock_config.execution,
            guardrail_config=mock_config.guardrails,
            optimization_config=mock_config.optimizations,
        )
        
        # Enable LLM in config
        mock_config.llm.enabled = True
        
        # Setup Agent
        agent = RecursiveAgent(
            fs_helper=fs_helper,
            executor=executor,
            optimization_config=mock_config.optimizations,
            llm_config=mock_config.llm,
        )
        
        # Inject REAL LLM client
        agent.code_generator._llm_client = live_llm_client
        agent.code_generator._model_name = "gpt-4o" # Use a smart model for code gen
        
        return agent

    def test_live_infinite_context(self, agent, tmp_path):
        """
        [LIVE] Verify Agent can write code to search a file using RLM.
        This tests:
        1. Code Generation (LLM writes the loop)
        2. RLM recursion (LLM answers 'ask_llm' calls)
        3. Execution (Monty runs it)
        """
        # 1. Prepare context file
        context_file = tmp_path / "live_data.txt"
        secret = "The secret password is: BLUE_ORCHID"
        # Hide it in some noise
        content = "Log line 1\n" * 50 + secret + "\n" + "Log line X\n" * 50
        context_file.write_text(content)
        
        # 2. Execute Task
        task = "Find the secret password in CONTEXT_DATA"
        
        print("\n[Live] Executing RLM task against real model...")
        result, output, error = agent.execute_recursive_task(
            task_description=task,
            context_data=context_file,
            verbose=True
        )
        
        assert error is None
        assert result == ExecutionResult.SUCCESS
        assert "BLUE_ORCHID" in output or "BLUE_ORCHID" in str(output)

    def test_live_rlm_with_tools(self, agent, temp_servers):
        """
        [LIVE] Verify Agent can use tools with RLM.
        This tests:
        1. Tool Discovery & Selection (Real LLM)
        2. Tool Code Generation (Real LLM)
        3. Tool Inlining (Monty)
        4. Execution
        """
        # 1. Create a real tool in the temp directory
        from pathlib import Path
        calc_dir = Path(temp_servers) / "calculator"
        calc_dir.mkdir(parents=True)
        (calc_dir / "multiply.py").write_text("def multiply(a, b): return a * b")
        (calc_dir / "__init__.py").write_text("from .multiply import multiply")
        
        # 2. Prepare Context (number to multiply)
        # We'll rely on the agent to read this or just know it from the task
        task = "Calculate 123 * 45 using the calculator tool"
        
        print("\n[Live] Executing RLM Tool task against real model...")
        
        # We need to force discovery or ensure the tool is found
        # The agent helper's discover_tools will scan temp_servers
        
        result, output, error = agent.execute_recursive_task(
            task_description=task,
            context_data=None, # No large context needed for this test
            verbose=True
        )
        
        assert error is None
        assert result == ExecutionResult.SUCCESS
        # 123 * 45 = 5535
        assert "5535" in output or "5535" in str(output)
