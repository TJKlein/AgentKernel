"""Recursive Agent implementation for infinite context tasks.

This module implements the Recursive Language Model (RLM) pattern, treating context
as a variable in the environment that can be programmatically inspected and
recursively queried by the LLM.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from client.agent_helper import AgentHelper
from client.code_generator import CodeGenerator
from config.schema import LLMConfig
import os

logger = logging.getLogger(__name__)

class RecursiveAgent(AgentHelper):
    """Agent that handles infinite context using recursive calls."""

    def __init__(self, *args, **kwargs):
        """Initialize recursive agent."""
        super().__init__(*args, **kwargs)
        self.context_data = None
        
        # Ensure we have an LLM client
        if self.llm_config and self.llm_config.enabled:
            # CodeGenerator already initializes connection, but we might need 
            # a direct client for the 'ask_llm' callback. 
            # We can reuse the one from CodeGenerator if accessible, or create new one.
            pass

    def execute_recursive_task(
        self, 
        task_description: str, 
        context_data: Union[str, Path],
        verbose: bool = True,
        required_tools: Optional[Dict[str, List[str]]] = None
    ) -> Any:
        """Execute a task with large context using RLM pattern.
        
        Args:
            task_description: The goal (e.g. "Find the error code")
            context_data: The large context (string or Path to file)
            verbose: Whether to print progress
            required_tools: Optional explicit tools to use
            
        Returns:
            Execution result
        """
        # Load context data
        if isinstance(context_data, Path) or (isinstance(context_data, str) and os.path.exists(context_data)):
            try:
                with open(context_data, "r", encoding="utf-8") as f:
                    self.context_data = f.read()
            except Exception as e:
                return None, None, f"Failed to load context file: {e}"
        else:
            self.context_data = context_data

        # Define the recursive callback
        def ask_llm(prompt: str, data: str) -> str:
            """Recursive callback to query LLM with a chunk of data."""
            if verbose:
                print(f"\n[RLM] ask_llm called with prompt: '{prompt}' and data length: {len(data)}")
            
            # Construct a prompt for the recursive call
            # We use the CodeGenerator's LLM client if available
            if not self.code_generator._llm_client:
                return "Error: LLM client not initialized"
                
            full_prompt = f"Context:\n{data}\n\nQuestion: {prompt}\n\nAnswer:"
            
            try:
                # Use same config as main agent
                completion_params = {
                    "model": self.code_generator._model_name,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant. Answer the question based on the context provided."},
                        {"role": "user", "content": full_prompt}
                    ],
                    "temperature": 0.0, # Deterministic for data extraction
                }
                 # Check if model supports max_completion_tokens (newer models)
                if hasattr(self.llm_config, 'max_completion_tokens') and self.llm_config.max_completion_tokens:
                    completion_params["max_completion_tokens"] = self.llm_config.max_completion_tokens
                else:
                    completion_params["max_completion_tokens"] = self.llm_config.max_tokens

                response = self.code_generator._llm_client.chat.completions.create(**completion_params)
                answer = response.choices[0].message.content.strip()
                if verbose:
                    print(f"[RLM] Answer: {answer[:100]}...")
                return answer
            except Exception as e:
                logger.error(f"ask_llm failed: {e}")
                return f"Error during LLM call: {e}"

        # Prepare context for execution
        # Prepare context for execution
        execution_context = {
            "inputs": {},
            "functions": {
                "ask_llm": ask_llm
            }
        }
        
        if self.context_data is not None:
             execution_context["inputs"]["CONTEXT_DATA"] = self.context_data
             
             # Modify task description to include RLM instructions
             rlm_instructions = (
                "\n\nIMPORTANT: The relevant context is loaded into the variable 'CONTEXT_DATA'. "
                "It is too large to read at once. "
                "Write Python code to inspect, slice, or search this variable. "
                "To reason about a specific chunk of data, usage the 'ask_llm(question, chunk_string)' function. "
                "Do NOT print the entire CONTEXT_DATA. "
                "Example pattern:\n"
                "chunk_size = 2000\n"
                "chunks = [CONTEXT_DATA[i:i+chunk_size] for i in range(0, len(CONTEXT_DATA), chunk_size)]\n"
                "for chunk in chunks:\n"
                "    result = ask_llm('Does this contain error X?', chunk)\n"
                "    if 'yes' in result.lower(): print(result)\n"
            )
             full_task = task_description + rlm_instructions
        else:
            full_task = task_description
        
        # We need a way to tell code_generator NOT to generate imports for ask_llm
        # or CONTEXT_DATA, as they are injected.
        # Currently CodeGenerator generates tool imports.
        # We can pass empty required_tools if we only use RLM, or mix them.
        
        # For now, let's use the standard flow but with our augmented task.
        # The CodeGenerator might try to find tools.
        
        # These variables are not defined in the original context, assuming they are meant to be empty or defined elsewhere.
        task_specific_calls = "" 
        extended_header = ""

        code = self.code_generator.generate_complete_code(
            required_tools=required_tools,
            task_description=full_task, # Use full_task here, not original task_description
            task_specific_calls=task_specific_calls,
            header_comment=extended_header,
        )
        
        # Post-process code for Monty (inline tools, remove incompatible imports)
        # This is a hack because Monty doesn't support file-based imports well yet
        if hasattr(self.executor, "execution_config") and self.executor.execution_config.sandbox_type == "monty":
             # 1. Inline required tools
            tool_code_prelude = ""
            lines = code.splitlines()
            new_lines = []
            
            for line in lines:
                # Remove traceback and mcp_client imports (not available/needed in Monty)
                if "import traceback" in line or "traceback.print_exc" in line:
                    continue
                if "client.mcp_client" in line:
                    indentation = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f"{indentation}pass # {line.strip()} # INLINED")
                    continue
                
                # Check for tool imports to inline
                # Pattern: from servers.{server}.{tool} import {func}
                # or from servers.{server} import {func}
                if line.strip().startswith("from servers."):
                    # Comment out the import and add pass to keep block valid, preserving indentation
                    indentation = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f"{indentation}pass # {line.strip()} # INLINED")
                    
                    try:
                        # Extract server and tool
                        parts = line.strip().split()
                        # parts[1] is 'servers.calculator.multiply' or 'servers.calculator'
                        module_path = parts[1].split(".")
                        if len(module_path) >= 2:
                            server_name = module_path[1]
                            tool_name = parts[3] # import {tool_name}
                            
                            # Read tool source
                            # Tool file is usually servers/{server}/{tool}.py
                            # But sometimes it's mapped differently. 
                            # Let's try reading the file.
                            tool_source = self.fs_helper.read_tool_file(server_name, tool_name)
                            if tool_source:
                                tool_code_prelude += f"\n# Tool: {tool_name}\n{tool_source}\n"
                            else:
                                # Try implicit tool name from file (e.g. imports)
                                pass
                    except Exception as e:
                        logger.warning(f"Failed to inline tool from line '{line}': {e}")
                else:
                    new_lines.append(line)
            
            code = tool_code_prelude + "\n".join(new_lines)
        
        # Execute with context
        # We need to access self.context_data and ask_llm if not passed explicitly,
        # but better to pass them via the specialized execute_recursive_task method
        # which constructs 'execution_context'.
        
        # Execute using parent's execute_task with our context
        return self.executor.execute(code, context=execution_context)

