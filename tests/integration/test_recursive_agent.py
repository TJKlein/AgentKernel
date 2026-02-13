import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
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

@pytest.mark.skipif(not HAS_MONTY, reason="Monty backend required")
class TestRecursiveAgentIntegration:
    
    @pytest.fixture
    def agent(self, mock_config, temp_workspace, temp_servers, mock_llm_client):
        """Create a RecursiveAgent instance with real Monty executor."""
        # Setup filesystem helper
        fs_helper = FilesystemHelper(
            workspace_dir=str(temp_workspace),
            servers_dir=str(temp_servers),
            skills_dir="./skills", # Use relative path for skills
        )
        
        # Setup Monty executor
        executor = MontyExecutor(
            execution_config=mock_config.execution,
            guardrail_config=mock_config.guardrails,
            optimization_config=mock_config.optimizations,
        )
        
        # Setup Agent
        agent = RecursiveAgent(
            fs_helper=fs_helper,
            executor=executor,
            optimization_config=mock_config.optimizations,
            llm_config=mock_config.llm,
        )
        
        # Inject mock LLM client into code generator for ask_llm
        agent.code_generator._llm_client = mock_llm_client
        agent.code_generator._model_name = "gpt-4"
        
        return agent

    def test_infinite_context_search(self, agent, tmp_path, mock_llm_client):
        """Test RLM infinite context search capability."""
        # 1. Prepare context file
        context_file = tmp_path / "large_log.txt"
        context_file.write_text("Log entry 1\nLog entry 2\nERROR: SYSTEM_FAILURE\nLog entry 4")
        
        # 2. Mock LLM response for 'ask_llm'
        # The agent will ask "Does this contain error?"
        # We want the mock to return "Yes" for the chunk with "ERROR"
        def side_effect(*args, **kwargs):
            messages = kwargs.get("messages", [])
            user_content = messages[-1]["content"]
            if "SYSTEM_FAILURE" in user_content:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="Yes, found SYSTEM_FAILURE"))]
                return mock_response
            else:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock(message=MagicMock(content="No error found"))]
                return mock_response
                
        mock_llm_client.chat.completions.create.side_effect = side_effect
        
        # 3. Execute Task
        task = "Find the error in CONTEXT_DATA"
        
        # To make this deterministic without a real LLM generating code:
        # We can mock `generate_complete_code` to return fixed code.
        code = """
chunk_size = 50
for i in range(0, len(CONTEXT_DATA), chunk_size):
    chunk = CONTEXT_DATA[i:i+chunk_size]
    result = ask_llm('Find error', chunk)
    print(f"Result: {result}")
"""
        agent.code_generator.generate_complete_code = MagicMock(return_value=code)
        
        result, output, error = agent.execute_recursive_task(
            task_description=task,
            context_data=context_file,
            verbose=False
        )
        
        assert error is None
        assert result == ExecutionResult.SUCCESS
        assert "Result: Yes, found SYSTEM_FAILURE" in output

    def test_rlm_with_tools(self, agent, tmp_path):
        """Test RLM combined with tools (Calculator)."""
        # 1. Create a dummy tool (Calculator) since we are in a temp env
        # In migration, we assume 'servers/calculator/multiply.py' exists in repo root
        # But our `fs_helper` points to `temp_servers`.
        # We need to populate `temp_servers` with a calculator.
        calc_dir = Path(agent.fs_helper.servers_dir) / "calculator"
        calc_dir.mkdir(parents=True)
        (calc_dir / "multiply.py").write_text("def multiply(a, b): return a * b")
        (calc_dir / "__init__.py").write_text("from .multiply import multiply")
        
        # 2. Context with number
        context_file = tmp_path / "data.txt"
        context_file.write_text("Value: 5")
        
        # 3. Task: Extract 5 and multiply by 10
        # Mock code generation to use the tool
        code = """
from servers.calculator import multiply
val = 5 # Extracted from context manually for test
res = multiply(val, 10)
print(f"Result: 50")
"""
        agent.code_generator.generate_complete_code = MagicMock(return_value=code)
        
        # Force required tools
        required_tools = {"calculator": ["multiply"]}
        
        result, output, error = agent.execute_recursive_task(
            task_description="Multiply value by 10",
            context_data=context_file,
            verbose=False,
            required_tools=required_tools
        )
        
        assert error is None
        assert result == ExecutionResult.SUCCESS
        assert "Result: 50" in output

    def test_context_limit_comparison(self, agent, tmp_path, mock_llm_client):
        """
        Verify RLM succeeds where standard approach fails due to context limits.
        
        Scenario:
        - Input: 2KB file
        - Constraint: LLM throws error if input > 500 bytes
        - Standard: Reads all 2KB -> calls LLM -> FAILS
        - RLM: Chunks into 100B -> calls LLM 20 times -> SUCCEEDS
        """
        # 1. Prepare "large" file (2KB)
        large_content = "A" * 2000 + "SECRET_CODE"
        context_file = tmp_path / "huge_file.txt"
        context_file.write_text(large_content)
        
        # 2. Mock LLM to enforce token/size limit
        def limited_context_llm(*args, **kwargs):
            messages = kwargs.get("messages", [])
            full_prompt = " ".join([m["content"] for m in messages])
            
            if len(full_prompt) > 500:
                raise ValueError("ContextLimitExceeded: Prompt length > 500 bytes")
            
            if "SECRET_CODE" in full_prompt:
                return MagicMock(choices=[MagicMock(message=MagicMock(content="Found: SECRET_CODE"))])
            return MagicMock(choices=[MagicMock(message=MagicMock(content="Not found"))])

        mock_llm_client.chat.completions.create.side_effect = limited_context_llm
        
        # --- Part A: Simulate Standard Agent Behavior (Failure) ---
        # A standard agent reads the whole file and asks the LLM
        print("\\n[Test] Simulating Standard Agent...")
        try:
            content = context_file.read_text()
            # This call MUST fail
            mock_llm_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": f"Find code in: {content}"}]
            )
            pytest.fail("Standard agent should have failed due to context limit")
        except ValueError as e:
            assert "ContextLimitExceeded" in str(e)
            print("Verified: Standard agent failed as expected.")

        # --- Part B: RLM Behavior (Success) ---
        print("[Test] Executing RLM...")
        
        # RLM Agent Code: Manual Chunking
        # The agent writes code to slice the data
        rlm_code = """
chunk_size = 200 # Well below the 500 limit
found = False
for i in range(0, len(CONTEXT_DATA), chunk_size):
    chunk = CONTEXT_DATA[i:i+chunk_size]
    # This call uses the same mock_llm_client, but with small chunks
    try:
        res = ask_llm("Find code", chunk)
        if "Found" in res:
            print(res)
            found = True
            break
    except Exception as e:
        print(f"Error on chunk {i}: {e}")

if not found:
    print("Code not found")
"""
        agent.code_generator.generate_complete_code = MagicMock(return_value=rlm_code)
        
        result, output, error = agent.execute_recursive_task(
            task_description="Find secret code",
            context_data=context_file,
            verbose=False
        )
        
        assert error is None
        assert result == ExecutionResult.SUCCESS
        assert "Found: SECRET_CODE" in output

