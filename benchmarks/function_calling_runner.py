"""Function Calling (FC) baseline runner for PTC-Bench.

This module implements the traditional Function Calling paradigm where:
1. The LLM is given a task and available tools (as JSON schemas)
2. The LLM emits tool calls as JSON
3. The framework executes the tools
4. Results are fed back to the LLM
5. Process repeats until the task is complete

This allows direct comparison with Programmatic Tool Calling (PTC).
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import litellm for LLM calls
try:
    import litellm
    litellm.drop_params = True
    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    logger.warning("litellm not available. Function calling baseline will be disabled.")


class FunctionCallingRunner:
    """Runner for Function Calling baseline.
    
    Implements the traditional tool-calling loop:
    - LLM sees task + tool schemas
    - LLM outputs JSON tool calls
    - Framework executes tools
    - Results fed back
    - Repeat until done
    """
    
    def __init__(
        self,
        llm_config=None,
        max_steps: int = 10,
        timeout: int = 60,
    ):
        """Initialize Function Calling runner.
        
        Args:
            llm_config: LLM configuration (provider, model, etc.)
            max_steps: Maximum number of LLM-tool interaction steps
            timeout: Maximum time for the entire task
        """
        self.llm_config = llm_config
        self.max_steps = max_steps
        self.timeout = timeout
        
        # Cost tracking (rough estimates)
        self.input_token_cost = 0.000005  # $5 per million input tokens
        self.output_token_cost = 0.000015  # $15 per million output tokens
        
        if llm_config and llm_config.enabled and HAS_LITELLM:
            self._model_name = llm_config.model
            if llm_config.provider == "azure_openai":
                if not self._model_name.startswith("azure/"):
                    self._model_name = f"azure/{self._model_name}"
            
            self._api_key = llm_config.api_key or os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            self._api_base = llm_config.azure_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
            self._api_version = llm_config.azure_api_version or os.environ.get("AZURE_OPENAI_API_VERSION")
        else:
            self._model_name = None
    
    def _get_tool_schemas(self, task) -> List[Dict[str, Any]]:
        """Extract tool schemas from task for FC mode.
        
        For PTC tasks, we convert the available tools to JSON schemas
        that the FC approach can use.
        """
        schemas = []
        
        # If task has explicit tool definitions in approaches.function_calling.tools
        if hasattr(task, 'approaches') and task.approaches:
            fc_config = task.approaches.get('function_calling', {})
            tools = fc_config.get('tools', [])
            for tool in tools:
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool['name'],
                        "description": tool.get('description', ''),
                        "parameters": tool.get('parameters', {"type": "object", "properties": {}})
                    }
                })
        
        # Fallback: infer tools from PTC setup files
        if not schemas and hasattr(task, 'setup_files'):
            for file_def in task.setup_files:
                if 'mock_mcp_client' in file_def.get('source', ''):
                    # Standard calculator/weather/database tools
                    schemas = self._get_default_tool_schemas()
                    break
        
        return schemas
    
    def _get_default_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get default tool schemas for common benchmark tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculator_add",
                    "description": "Add two numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "number"},
                            "b": {"type": "number"}
                        },
                        "required": ["a", "b"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculator_calculate",
                    "description": "Evaluate a mathematical expression",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string"}
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "weather_get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filesystem_read_file",
                    "description": "Read contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filesystem_write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "database_query",
                    "description": "Execute a SQL query",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
    
    def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Tuple[Any, int]:
        """Execute a single tool call and return result with retry count.
        
        Returns:
            Tuple of (result, retry_count)
        """
        function_name = tool_call.get('name', '')
        arguments = tool_call.get('arguments', {})
        
        # Map function names to actual implementations
        # This simulates what a real FC framework would do
        try:
            if function_name == 'calculator_add':
                result = arguments.get('a', 0) + arguments.get('b', 0)
                return {"result": result}, 0
            
            elif function_name == 'calculator_calculate':
                # Safe eval for expressions
                expression = arguments.get('expression', '')
                result = eval(expression, {"__builtins__": {}}, {})
                return {"result": result}, 0
            
            elif function_name == 'weather_get_weather':
                location = arguments.get('location', '')
                units = arguments.get('units', 'celsius')
                # Mock weather response
                return {
                    "location": location,
                    "temperature": 22 if units == 'celsius' else 72,
                    "unit": units,
                    "condition": "sunny"
                }, 0
            
            elif function_name == 'filesystem_read_file':
                path = arguments.get('path', '')
                try:
                    with open(path, 'r') as f:
                        return {"content": f.read()}, 0
                except Exception as e:
                    return {"error": str(e)}, 0
            
            elif function_name == 'filesystem_write_file':
                path = arguments.get('path', '')
                content = arguments.get('content', '')
                with open(path, 'w') as f:
                    f.write(content)
                return {"status": "success"}, 0
            
            elif function_name == 'database_query':
                query = arguments.get('query', '')
                # Mock database response
                return {"rows": [{"id": 1, "name": "test"}], "count": 1}, 0
            
            else:
                return {"error": f"Unknown function: {function_name}"}, 0
                
        except Exception as e:
            return {"error": str(e)}, 0
    
    def _run_task_text_based(self, task, tool_schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run task using text-based function calling for models without native tool support."""
        start_time = time.time()
        
        # Build tool descriptions as text
        tool_descriptions = []
        for schema in tool_schemas:
            func = schema.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            tool_descriptions.append(f"- {name}({params}): {desc}")
        
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."
        
        messages = [
            {"role": "system", "content": f"""You are an AI assistant that uses tools to complete tasks.

Available tools:
{tools_text}

To use a tool, respond with:
TOOL_CALL: {{"name": "tool_name", "arguments": {{"arg1": "value1"}}}}

After the final result, respond with:
FINAL_ANSWER: your final answer"""},
            {"role": "user", "content": task.description}
        ]
        
        llm_calls = 0
        tool_calls = 0
        retries = 0
        total_input_tokens = 0
        total_output_tokens = 0
        final_output = ""
        
        try:
            for step in range(self.max_steps):
                if time.time() - start_time > self.timeout:
                    break
                
                response = litellm.completion(
                    model=self._model_name,
                    messages=messages,
                    temperature=0.3,
                    api_key=self._api_key,
                    api_base=self._api_base,
                    api_version=self._api_version,
                    max_tokens=1000,
                )
                
                llm_calls += 1
                total_input_tokens += response.usage.prompt_tokens if hasattr(response, 'usage') else 0
                total_output_tokens += response.usage.completion_tokens if hasattr(response, 'usage') else 0
                
                content = response.choices[0].message.content.strip()
                messages.append({"role": "assistant", "content": content})
                
                # Check for tool call
                if "TOOL_CALL:" in content:
                    # Extract tool call
                    tool_match = content.split("TOOL_CALL:")[1].split("\n")[0].strip()
                    try:
                        tool_call = json.loads(tool_match)
                        tool_calls += 1
                        
                        result, retry_count = self._execute_tool_call(tool_call)
                        retries += retry_count
                        
                        # Add result to messages
                        messages.append({
                            "role": "user",
                            "content": f"Tool result: {json.dumps(result)}"
                        })
                    except (json.JSONDecodeError, IndexError) as e:
                        messages.append({
                            "role": "user",
                            "content": f"Error parsing tool call: {str(e)}"
                        })
                
                # Check for final answer
                elif "FINAL_ANSWER:" in content:
                    final_output = content.split("FINAL_ANSWER:")[1].strip()
                    break
                else:
                    # Assume this is the final answer
                    final_output = content
                    break
            
            execution_time = time.time() - start_time
            cost = self._calculate_cost(total_input_tokens, total_output_tokens)
            
            return {
                "success": True,
                "output": final_output,
                "error": None,
                "execution_time": execution_time,
                "llm_calls": llm_calls,
                "tool_calls": tool_calls,
                "retries": retries,
                "cost": cost
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            cost = self._calculate_cost(total_input_tokens, total_output_tokens)
            
            return {
                "success": False,
                "output": final_output,
                "error": f"Text-based FC failed: {str(e)}",
                "execution_time": execution_time,
                "llm_calls": llm_calls,
                "tool_calls": tool_calls,
                "retries": retries,
                "cost": cost
            }

    def run_task(self, task) -> Dict[str, Any]:
        """Run a single task using Function Calling paradigm.
        
        Args:
            task: Task object with description, expected output, etc.
            
        Returns:
            Dictionary with results:
            - success: bool
            - output: str
            - error: Optional[str]
            - execution_time: float
            - llm_calls: int
            - tool_calls: int
            - retries: int
            - cost: float
        """
        if not HAS_LITELLM or not self._model_name:
            return {
                "success": False,
                "output": "",
                "error": "Function Calling baseline requires litellm and valid LLM config",
                "execution_time": 0.0,
                "llm_calls": 0,
                "tool_calls": 0,
                "retries": 0,
                "cost": 0.0
            }
        
        start_time = time.time()
        
        tool_schemas = self._get_tool_schemas(task)
        
        # Build conversation history
        messages = [
            {"role": "system", "content": "You are an AI assistant that uses tools to complete tasks. You can make multiple tool calls in sequence. Always provide your final answer in the last message."},
            {"role": "user", "content": task.description}
        ]
        
        llm_calls = 0
        tool_calls = 0
        retries = 0
        total_input_tokens = 0
        total_output_tokens = 0
        final_output = ""
        
        try:
            for step in range(self.max_steps):
                # Check timeout
                if time.time() - start_time > self.timeout:
                    break
                
                # Call LLM with tools
                try:
                    response = litellm.completion(
                        model=self._model_name,
                        messages=messages,
                        tools=tool_schemas if tool_schemas else None,
                        tool_choice="auto" if tool_schemas else None,
                        temperature=0.3,
                        api_key=self._api_key,
                        api_base=self._api_base,
                        api_version=self._api_version,
                    )
                    
                    llm_calls += 1
                    total_input_tokens += response.usage.prompt_tokens if hasattr(response, 'usage') else 0
                    total_output_tokens += response.usage.completion_tokens if hasattr(response, 'usage') else 0
                    
                    message = response.choices[0].message
                    
                    # Check if tool calls were made
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        # Add assistant message with tool calls
                        messages.append({
                            "role": "assistant",
                            "content": message.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments
                                    }
                                }
                                for tc in message.tool_calls
                            ]
                        })
                        
                        # Execute each tool call
                        for tc in message.tool_calls:
                            tool_calls += 1
                            
                            try:
                                arguments = json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                arguments = {}
                            
                            tool_call = {
                                "name": tc.function.name,
                                "arguments": arguments
                            }
                            
                            result, retry_count = self._execute_tool_call(tool_call)
                            retries += retry_count
                            
                            # Add tool result to messages
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": json.dumps(result)
                            })
                    
                    else:
                        # No tool calls - task is complete
                        final_output = message.content or ""
                        messages.append({
                            "role": "assistant",
                            "content": final_output
                        })
                        break
                        
                except Exception as e:
                    error_str = str(e)
                    # If this is the first call and tools might not be supported, fall back to text-based
                    if step == 0 and tool_schemas and ("badrequest" in error_str.lower() or "tools" in error_str.lower() or "function" in error_str.lower()):
                        return self._run_task_text_based(task, tool_schemas)
                    
                    return {
                        "success": False,
                        "output": final_output,
                        "error": f"LLM call failed: {error_str}",
                        "execution_time": time.time() - start_time,
                        "llm_calls": llm_calls,
                        "tool_calls": tool_calls,
                        "retries": retries,
                        "cost": self._calculate_cost(total_input_tokens, total_output_tokens)
                    }
            
            execution_time = time.time() - start_time
            cost = self._calculate_cost(total_input_tokens, total_output_tokens)
            
            return {
                "success": True,  # Will be validated separately
                "output": final_output,
                "error": None,
                "execution_time": execution_time,
                "llm_calls": llm_calls,
                "tool_calls": tool_calls,
                "retries": retries,
                "cost": cost
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            cost = self._calculate_cost(total_input_tokens, total_output_tokens)
            
            return {
                "success": False,
                "output": final_output,
                "error": str(e),
                "execution_time": execution_time,
                "llm_calls": llm_calls,
                "tool_calls": tool_calls,
                "retries": retries,
                "cost": cost
            }
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate approximate cost based on token usage."""
        return (input_tokens * self.input_token_cost + 
                output_tokens * self.output_token_cost)


def run_task_function_calling(task, llm_config=None) -> Dict[str, Any]:
    """Convenience function to run a task with Function Calling.
    
    Args:
        task: Task object
        llm_config: LLM configuration
        
    Returns:
        Result dictionary
    """
    runner = FunctionCallingRunner(llm_config=llm_config)
    return runner.run_task(task)
