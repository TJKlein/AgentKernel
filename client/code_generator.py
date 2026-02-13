"""Code generation utilities for creating tool usage code.

This module provides generic code generation capabilities that can be used
by any example or agent to generate Python code that uses discovered tools.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None  # type: ignore
    logger.warning("openai package not available. LLM-based code generation will be disabled.")


class CodeGenerator:
    """Generic code generator for tool usage."""

    def __init__(
        self,
        include_error_handling: bool = True,
        llm_config: Optional[Any] = None,  # LLMConfig from config.schema
        tool_descriptions: Optional[Dict[tuple, str]] = None,
    ):
        """Initialize code generator.

        Args:
            include_error_handling: Whether to wrap tool calls in try-except blocks
            llm_config: Optional LLMConfig for LLM-based code generation
            tool_descriptions: Optional dict mapping (server_name, tool_name) to descriptions
        """
        self.include_error_handling = include_error_handling
        self.llm_config = llm_config
        self.tool_descriptions = tool_descriptions or {}
        self._llm_client = None
        
        # Initialize LLM client if enabled
        if llm_config and llm_config.enabled and HAS_OPENAI:
            self._init_llm_client()
    
    def _init_llm_client(self):
        """Initialize OpenAI client based on config."""
        if not self.llm_config or not HAS_OPENAI:
            return
        
        try:
            # Try Azure API key first, then fallback to OpenAI API key
            api_key = (
                self.llm_config.api_key or 
                os.environ.get("AZURE_OPENAI_API_KEY") or 
                os.environ.get("OPENAI_API_KEY")
            )
            if not api_key:
                logger.warning("LLM enabled but no API key found. Falling back to rule-based generation.")
                return
            
            if self.llm_config.provider == "azure_openai":
                from openai import AzureOpenAI
                if not self.llm_config.azure_endpoint:
                    logger.warning("Azure OpenAI enabled but no endpoint configured.")
                    return
                if not self.llm_config.azure_deployment_name:
                    logger.warning("Azure OpenAI enabled but no deployment name configured.")
                    return
                self._llm_client = AzureOpenAI(
                    api_key=api_key,
                    api_version=self.llm_config.azure_api_version,
                    azure_endpoint=self.llm_config.azure_endpoint,
                )
                self._model_name = self.llm_config.azure_deployment_name
            else:
                self._llm_client = OpenAI(api_key=api_key)
                self._model_name = self.llm_config.model
            
            logger.info(f"Initialized LLM client: {self.llm_config.provider} / {self._model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize LLM client: {e}. Falling back to rule-based generation.")
            self._llm_client = None

    def generate_imports(self, required_tools: Dict[str, List[str]]) -> List[str]:
        """Generate import statements for required tools.

        Args:
            required_tools: Dict mapping server names to lists of tool names

        Returns:
            List of import statements
        """
        import_statements = []
        required_tools = required_tools or {}
        for server_name, tools in required_tools.items():
            if tools:
                tool_imports = ", ".join(tools)
                import_statements.append(f"from servers.{server_name} import {tool_imports}")
        return import_statements

    def generate_usage_code(
        self,
        required_tools: Dict[str, List[str]],
        task_description: str = "",
        task_specific_calls: Optional[Dict[str, str]] = None,
    ) -> List[str]:
        """Generate usage code blocks for required tools.

        Args:
            required_tools: Dict mapping server names to lists of tool names
            task_description: Description of the task (for smart code generation)
            task_specific_calls: Optional dict mapping server names to custom code blocks

        Returns:
            List of code blocks (strings)
        """
        usage_code = []
        required_tools = required_tools or {}
        for server_name, tools in required_tools.items():
            if not tools:
                continue

            # Check if there's task-specific code for this server
            if task_specific_calls and server_name in task_specific_calls:
                usage_code.append(task_specific_calls[server_name])
                continue

            # Generate smart usage code based on server and tools
            tool_calls = []
            for tool_name in tools:
                # Generate appropriate calls based on tool name and task
                call_code = self._generate_smart_tool_call(server_name, tool_name, task_description)
                if call_code:
                    tool_calls.append(call_code)

            if tool_calls:
                usage_code.append("\n".join(tool_calls) + "\n")

        return usage_code

    def _generate_smart_tool_call(
        self, server_name: str, tool_name: str, task_description: str
    ) -> str:
        """Generate smart tool call code based on tool name and task."""
        # Calculator tools
        if server_name == "calculator":
            if tool_name == "add":
                return """# Calculate 5 + 3
try:
    result = add(5, 3)
    print(f"Result: 5 + 3 = {result}")
except Exception as e:
    print(f"Error calling add: {e}")
    import traceback
    traceback.print_exc()"""
            elif tool_name == "calculate":
                return """# Calculate expression
try:
    result = calculate("5 + 3")
    print(f"Result: 5 + 3 = {result}")
except Exception as e:
    print(f"Error calling calculate: {e}")
    import traceback
    traceback.print_exc()"""
            elif tool_name == "multiply":
                return """# Multiply numbers
try:
    result = multiply(4, 7)
    print(f"Result: 4 * 7 = {result}")
except Exception as e:
    print(f"Error calling multiply: {e}")
    import traceback
    traceback.print_exc()"""

        # Weather tools
        elif server_name == "weather":
            if tool_name == "get_weather":
                return """# Get current weather
try:
    weather = get_weather(location="San Francisco, CA", units="celsius")
    print(f"\\nWeather in {weather['location']}:")
    print(f"  Temperature: {weather['temperature']}°{weather['unit']}")
    print(f"  Condition: {weather['condition']}")
    print(f"  Humidity: {weather['humidity']}%")
except Exception as e:
    print(f"Error calling get_weather: {e}")
    import traceback
    traceback.print_exc()"""
            elif tool_name == "get_forecast":
                return """# Get weather forecast
try:
    forecast = get_forecast(location="San Francisco, CA", days=3)
    print(f"\\nForecast for {forecast['location']} ({len(forecast['forecast'])} days):")
    for day in forecast['forecast'][:3]:
        print(f"  {day['date']}: {day['condition']}, High: {day['high']}°, Low: {day['low']}°")
except Exception as e:
    print(f"Error calling get_forecast: {e}")
    import traceback
    traceback.print_exc()"""

        # Database tools
        elif server_name == "database":
            if tool_name == "query":
                return """# Query database
results = query(sql="SELECT * FROM users LIMIT 5")
print(f"Query returned {len(results)} rows")
if results:
    print(f"Sample: {results[0]}")"""
            elif tool_name == "list_tables":
                return """# List database tables
tables = list_tables()
print(f"Found {len(tables)} tables: {tables}")"""

        # Filesystem tools
        elif server_name == "filesystem":
            if tool_name == "read_file":
                return """# Read file
try:
    content = read_file(path="/tmp/test.txt")
    print(f"File content: {content[:100]}...")
except Exception as e:
    print(f"Error reading file: {e}")"""
            elif tool_name == "write_file":
                return """# Write file
result = write_file(path="/tmp/test.txt", content="Hello, World!")
print(f"File written: {result}")"""
            elif tool_name == "list_directory":
                return """# List directory
result = list_directory(path="/tmp")
print(f"Directory contains {len(result.get('items', []))} items")"""

        # Generic fallback
        if self.include_error_handling:
            return f"""# Using {tool_name}
try:
    result = {tool_name}()
    print(f"{tool_name}() = {{result}}")
except Exception as e:
    print(f"{tool_name}() error: {{e}}")"""
        else:
            return f"""# Using {tool_name}
result = {tool_name}()
print(f"{tool_name}() = {{result}}")"""

    def _generate_code_with_llm(
        self,
        required_tools: Dict[str, List[str]],
        task_description: str,
        imports: List[str],
    ) -> Optional[str]:
        """Generate code using LLM.
        
        Args:
            required_tools: Dict mapping server names to lists of tool names
            task_description: Description of the task
            imports: List of import statements
            
        Returns:
            Generated code string or None if LLM generation fails
        """
        if not self._llm_client or not self.llm_config:
            return None
        
        try:
            # Build tool descriptions for prompt
            tool_info = []
            required_tools = required_tools or {}
            for server_name, tools in required_tools.items():
                for tool_name in tools:
                    key = (server_name, tool_name)
                    desc = self.tool_descriptions.get(key, f"{server_name}.{tool_name}")
                    tool_info.append(f"- {server_name}.{tool_name}: {desc}")
            
            tool_list = "\n".join(tool_info)
            imports_str = "\n".join(imports) if imports else "# No imports needed"
            
            prompt = f"""You are a code generator that creates Python code to execute tasks using available tools.

Task: {task_description}

Available tools:
{tool_list}

Import statements (already generated):
{imports_str}

Generate Python code that:
1. Uses the import statements above
2. Calls the appropriate tools to complete the task
3. Handles errors with try/except blocks
4. Prints results clearly
5. Follows Python best practices

Only generate the usage code (not the imports). The code should be executable and complete the task.

Generated code:"""

            # Use max_completion_tokens for newer models, max_tokens for older ones
            completion_params = {
                "model": self._model_name,
                "messages": [
                    {"role": "system", "content": "You are a helpful code generator that creates clean, executable Python code."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.llm_config.temperature,
            }
            
            # Check if model supports max_completion_tokens (newer models)
            # Use max_completion_tokens if available, otherwise fall back to max_tokens
            if hasattr(self.llm_config, 'max_completion_tokens') and self.llm_config.max_completion_tokens:
                completion_params["max_completion_tokens"] = self.llm_config.max_completion_tokens
            else:
                completion_params["max_tokens"] = self.llm_config.max_tokens
            
            response = self._llm_client.chat.completions.create(**completion_params)
            
            generated_code = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if generated_code.startswith("```python"):
                generated_code = generated_code[9:]
            elif generated_code.startswith("```"):
                generated_code = generated_code[3:]
            if generated_code.endswith("```"):
                generated_code = generated_code[:-3]
            generated_code = generated_code.strip()
            
            logger.info("Generated code using LLM")
            return generated_code
            
        except Exception as e:
            logger.warning(f"LLM code generation failed: {e}. Falling back to rule-based generation.")
            return None

    def generate_complete_code(
        self,
        required_tools: Dict[str, List[str]],
        task_description: str,
        task_specific_calls: Optional[Dict[str, str]] = None,
        header_comment: Optional[str] = None,
    ) -> str:
        """Generate complete Python code for tool usage.

        Args:
            required_tools: Dict mapping server names to lists of tool names
            task_description: Description of the task
            task_specific_calls: Optional dict mapping server names to custom code blocks
            header_comment: Optional header comment to include

        Returns:
            Complete Python code string
        """
        imports = self.generate_imports(required_tools)
        
        # Try LLM generation if enabled
        if self._llm_client and self.llm_config and self.llm_config.enabled:
            llm_usage = self._generate_code_with_llm(required_tools, task_description, imports)
            if llm_usage:
                usage = [llm_usage]
            else:
                # Fallback to rule-based
                usage = self.generate_usage_code(required_tools, task_description, task_specific_calls)
        else:
            # Use rule-based generation
            usage = self.generate_usage_code(required_tools, task_description, task_specific_calls)

        default_header = """# Import tools from filesystem (written by sandbox executor)
# https://www.anthropic.com/engineering/code-execution-with-mcp
"""

        header = header_comment or default_header

        # Wrap imports in try/except to show actual errors
        imports_with_error_handling = []
        if imports:
            # Import client first (servers depend on it)
            imports_with_error_handling.append("try:")
            imports_with_error_handling.append("    from client.mcp_client import call_mcp_tool")
            imports_with_error_handling.append("except Exception as e:")
            imports_with_error_handling.append(
                "    print(f'ERROR: Cannot import client.mcp_client: {type(e).__name__}: {e}', flush=True)"
            )
            imports_with_error_handling.append("    import traceback")
            imports_with_error_handling.append("    traceback.print_exc()")
            imports_with_error_handling.append("    call_mcp_tool = None")
            imports_with_error_handling.append("")
            # Now import server tools
            for imp in imports:
                imports_with_error_handling.append(f"try:")
                imports_with_error_handling.append(f"    {imp}")
                imports_with_error_handling.append(f"except Exception as e:")
                imports_with_error_handling.append(
                    f"    print(f'Import error: {{type(e).__name__}}: {{e}}', flush=True)"
                )
                imports_with_error_handling.append(f"    import traceback")
                imports_with_error_handling.append(f"    traceback.print_exc()")
                # Set variables to None if import fails
                if "from" in imp and "import" in imp:
                    import_part = imp.split("import")[-1].strip()
                    var_names = [v.strip() for v in import_part.split(",")]
                    for var_name in var_names:
                        imports_with_error_handling.append(f"    {var_name} = None")
                elif "import" in imp:
                    import_part = imp.split("import")[-1].strip()
                    if " as " in import_part:
                        var_name = import_part.split(" as ")[-1].strip()
                    else:
                        var_name = import_part.split(",")[0].strip()
                    imports_with_error_handling.append(f"    {var_name} = None")
        imports_str = (
            chr(10).join(imports_with_error_handling)
            if imports_with_error_handling
            else "# No tools needed for this task"
        )
        usage_str = chr(10).join(usage) if usage else "# No usage code generated"
        
        # Add file operations if task mentions saving/reading files
        file_ops = self._generate_file_operations(task_description)
        if file_ops:
            usage_str = usage_str + "\n\n" + file_ops

        # Code will be executed via script file (not REPL mode) to prevent breaking on errors
        # No need to wrap in function - the script file execution handles it
        code = (
            header
            + "\n"
            + imports_str
            + "\n\n# Execute the task using selected tools\n"
            + usage_str
            + "\n"
        )

        return code
    
    def _generate_file_operations(self, task_description: str) -> str:
        """Generate file operation code if task mentions file operations."""
        task_lower = task_description.lower()
        file_ops = []
        
        # Check for JSON file operations
        is_json = ".json" in task_description or "json" in task_lower
        
        # Check if this is a read+update operation first (prioritize over save)
        has_save_back = "save it back" in task_lower or "save back" in task_lower or "save it" in task_lower
        has_read = "read" in task_lower or "from" in task_lower
        has_update = "update" in task_lower or "continue" in task_lower
        has_create = "create" in task_lower or "initialize" in task_lower
        # Don't treat create/initialize as read+update - it's a new file creation
        is_read_update = (has_read or has_update or has_save_back) and not has_create and ("file" in task_lower or "workspace" in task_lower or "json" in task_lower)
        
        # Check for file save operations (only if not a read+update operation)
        if not is_read_update and ("save" in task_lower or has_create) and ("file" in task_lower or "workspace" in task_lower):
            # Extract filename from task
            import re
            # Look for patterns like "save ... to a file called 'workspace/result.txt'"
            # Also look for "/workspace/state.json" patterns (more specific)
            filename_match = re.search(r"(/workspace/[^\s'\"]+\.json)", task_description)
            if not filename_match:
                # Try patterns like "to /workspace/file.json" or "called '/workspace/file.json'"
                filename_match = re.search(r"(?:to|called|from)\s+(/workspace/[^\s'\"]+\.json)", task_description)
            if not filename_match:
                # Try quoted patterns
                filename_match = re.search(r"['\"](/workspace/[^'\"]+\.json)['\"]", task_description)
            if filename_match:
                filename = filename_match.group(1)
                # Clean up filename
                filename = filename.strip("'\"")
                # Ensure it starts with /workspace if it's a workspace file
                if not filename.startswith("/workspace") and "workspace" in filename:
                    filename = "/workspace/" + filename.replace("workspace/", "").lstrip("/")
                elif not filename.startswith("/") and "workspace" not in filename:
                    filename = "/workspace/" + filename
                
                # Check if it's a JSON file
                if is_json or filename.endswith(".json"):
                    # Generate JSON file creation code
                    # Try to extract JSON structure from task description
                    json_data_code = self._extract_json_structure(task_description, task_lower)
                    
                    # Check if we need to do calculations/updates after creating the structure
                    post_ops_code = ""
                    # Check for "add to results" operations (look for "add" and "results" and calculation)
                    if "add" in task_lower and "results" in task_lower:
                        calc_match = re.search(r"(\d+)\s*[+\-*/]\s*(\d+)", task_description)
                        if calc_match:
                            a, b = int(calc_match.group(1)), int(calc_match.group(2))
                            op_match = re.search(r"([+\-*/])", task_description)
                            op = op_match.group(1) if op_match else "*"
                            
                            if op == "+":
                                post_ops_code += f"\ncalc_result = {a} + {b}\n"
                            elif op == "-":
                                post_ops_code += f"\ncalc_result = {a} - {b}\n"
                            elif op == "*":
                                post_ops_code += f"\ncalc_result = {a} * {b}\n"
                            elif op == "/":
                                post_ops_code += f"\ncalc_result = {a} / {b}\n"
                            
                            post_ops_code += 'if "results" not in data:\n    data["results"] = []\ndata["results"].append(calc_result)\n'
                    
                    # Check for current_step update (look for "update" and "current_step" or "step")
                    if "update" in task_lower and ("current_step" in task_lower or "step" in task_lower):
                        # Try to find "update current_step to X" - prioritize update instructions over initial values
                        # Look for patterns like "Update current_step to 2" or "update current_step: 2"
                        step_match = re.search(r"update\s+current_step\s+(?:to|:)\s*(\d+)", task_description, re.IGNORECASE)
                        if not step_match:
                            # Fallback: look for "current_step to X" after "update"
                            step_match = re.search(r"update.*?current_step.*?(?:to|:)\s*(\d+)", task_description, re.IGNORECASE)
                        if step_match:
                            new_step = int(step_match.group(1))
                            post_ops_code += f'data["current_step"] = {new_step}\n'
                    
                    file_ops.append(f"""# Save data to JSON file
import json
import os
os.makedirs(os.path.dirname("{filename}"), exist_ok=True)
{json_data_code}{post_ops_code}
with open("{filename}", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print(f"✅ Saved JSON data to {filename}")""")
                # Check if we need to save a calculation result
                elif "calculate" in task_lower or "result" in task_lower:
                    file_ops.append(f"""# Save result to file
import os
os.makedirs(os.path.dirname("{filename}"), exist_ok=True)
with open("{filename}", "w") as f:
    f.write(str(result))
print(f"✅ Saved result to {filename}")""")
                else:
                    file_ops.append(f"""# Save to file
import os
os.makedirs(os.path.dirname("{filename}"), exist_ok=True)
with open("{filename}", "w") as f:
    f.write("result")
print(f"✅ Saved to {filename}")""")
        
        # Check for file read and update operations (for workflows)
        # This should have been checked above, but check again to be safe
        if is_read_update:
            # Extract filename from task
            import re
            # Look for JSON file path directly first (most specific)
            filename_match = re.search(r"(/workspace/[^\s'\"]+\.json)", task_description)
            if not filename_match:
                # Try patterns like "from /workspace/file.json" or "called '/workspace/file.json'"
                filename_match = re.search(r"(?:from|called|read)\s+(/workspace/[^\s'\"]+\.json)", task_description)
            if not filename_match:
                # Try quoted patterns
                filename_match = re.search(r"['\"](/workspace/[^'\"]+\.json)['\"]", task_description)
            if filename_match:
                filename = filename_match.group(1)
                filename = filename.strip("'\"")
                if not filename.startswith("/workspace") and "workspace" in filename:
                    filename = "/workspace/" + filename.replace("workspace/", "").lstrip("/")
                elif not filename.startswith("/") and "workspace" not in filename:
                    filename = "/workspace/" + filename
                
                # Check if it's a JSON file
                if filename.endswith(".json") or is_json:
                    # Check if we need to update the file after reading
                    has_save_back = "save it back" in task_lower or "save back" in task_lower or "save it" in task_lower
                    has_read = "read" in task_lower or "from" in task_lower
                    has_update = "update" in task_lower or "continue" in task_lower or "add" in task_lower
                    # Use read+update if task mentions reading, updating, or saving back
                    if has_read or has_update or has_save_back:
                        # Read, update, and save back
                        update_code = self._generate_json_update_code(task_description, task_lower, filename)
                        # Ensure update_code is not empty (at least a pass statement)
                        if not update_code or update_code.strip() == "# No updates needed":
                            update_code = "pass  # No updates needed"
                        file_ops.append(f"""# Read and update JSON file
import json
import os
try:
    with open("{filename}", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ Read JSON from {filename}:")
    print(json.dumps(data, indent=2))
    # Update data
{update_code}
    # Save updated data back
    with open("{filename}", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Updated and saved {filename}")
except FileNotFoundError:
    print(f"❌ File {filename} not found")
except json.JSONDecodeError as e:
    print(f"❌ Error parsing JSON from {filename}: {{e}}")
except Exception as e:
    print(f"❌ Error reading/updating {filename}: {{e}}")""")
                    else:
                        # Just read
                        file_ops.append(f"""# Read JSON file
import json
try:
    with open("{filename}", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✅ Read JSON from {filename}:")
    print(json.dumps(data, indent=2))
except FileNotFoundError:
    print(f"❌ File {filename} not found")
except json.JSONDecodeError as e:
    print(f"❌ Error parsing JSON from {filename}: {{e}}")
except Exception as e:
    print(f"❌ Error reading {filename}: {{e}}")""")
                else:
                    file_ops.append(f"""# Read file back
try:
    with open("{filename}", "r") as f:
        content = f.read()
    print(f"✅ Read from {filename}: {{content}}")
except FileNotFoundError:
    print(f"❌ File {filename} not found")
except Exception as e:
    print(f"❌ Error reading {filename}: {{e}}")""")
        
        # Check for mount verification
        if "mounted" in task_lower or "mount" in task_lower:
            file_ops.append("""# Check if /workspace is mounted
import os
workspace_path = "/workspace"
if os.path.exists(workspace_path):
    print(f"✅ {workspace_path} exists and is mounted")
    try:
        contents = os.listdir(workspace_path)
        print(f"   Contents: {contents}")
    except Exception as e:
        print(f"   Error listing contents: {e}")
else:
    print(f"❌ {workspace_path} does not exist (mount may have failed)")""")
        
        return "\n".join(file_ops) if file_ops else ""
    
    def _extract_json_structure(self, task_description: str, task_lower: str) -> str:
        """Extract JSON structure from task description and generate Python code.
        
        Args:
            task_description: Task description that may contain JSON structure
            task_lower: Lowercase version of task description
            
        Returns:
            Python code that creates the data dict
        """
        import re
        
        # Look for patterns like:
        # - calculation: "5 + 3"
        # - result: 8
        # - step: 1
        # - message: "State saved in session 1"
        
        code_lines = ["# Build JSON data structure", "data = {}"]
        
        # Pattern 1: Look for field: value patterns
        field_pattern = r"[-*]\s*(\w+):\s*([^\n]+)"
        matches = re.findall(field_pattern, task_description)
        
        if matches:
            # Check if we need to calculate result first
            needs_calculation = False
            calc_a, calc_b, calc_op = None, None, None
            if "calculate" in task_lower:
                calc_match = re.search(r"(\d+)\s*[+\-*/]\s*(\d+)", task_description)
                if calc_match:
                    calc_a, calc_b = int(calc_match.group(1)), int(calc_match.group(2))
                    op_match = re.search(r"([+\-*/])", task_description)
                    calc_op = op_match.group(1) if op_match else "+"
                    needs_calculation = True
            
            # Add calculation code if needed
            if needs_calculation:
                if calc_op == "+":
                    code_lines.append(f'calc_result = {calc_a} + {calc_b}')
                elif calc_op == "-":
                    code_lines.append(f'calc_result = {calc_a} - {calc_b}')
                elif calc_op == "*":
                    code_lines.append(f'calc_result = {calc_a} * {calc_b}')
                elif calc_op == "/":
                    code_lines.append(f'calc_result = {calc_a} / {calc_b}')
                else:
                    code_lines.append(f'calc_result = {calc_a} + {calc_b}')
            
            for field, value in matches:
                field = field.strip()
                value = value.strip()
                
                # Special handling for result field - use calculated value if available
                if field == "result" and needs_calculation:
                    code_lines.append(f'data["{field}"] = calc_result')
                    continue
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value_str = value[1:-1]
                    code_lines.append(f'data["{field}"] = "{value_str}"')
                elif value.startswith("'") and value.endswith("'"):
                    value_str = value[1:-1]
                    code_lines.append(f'data["{field}"] = "{value_str}"')
                else:
                    # Try to convert to number or list
                    try:
                        # Check if it's an empty list
                        if value.strip() == "[]":
                            code_lines.append(f'data["{field}"] = []')
                        # Check if it's a list with items
                        elif value.strip().startswith("[") and value.strip().endswith("]"):
                            # Try to parse as Python list
                            try:
                                import ast
                                parsed = ast.literal_eval(value.strip())
                                if isinstance(parsed, list):
                                    code_lines.append(f'data["{field}"] = {parsed}')
                                else:
                                    code_lines.append(f'data["{field}"] = "{value}"')
                            except:
                                code_lines.append(f'data["{field}"] = "{value}"')
                        # Try number
                        elif '.' in value:
                            code_lines.append(f'data["{field}"] = {float(value)}')
                        else:
                            code_lines.append(f'data["{field}"] = {int(value)}')
                    except ValueError:
                        # Keep as string
                        code_lines.append(f'data["{field}"] = "{value}"')
        
        # If we have matches, check if we need to add calculation
        if len(code_lines) > 1:  # More than just "data = {}"
            # Check if result field is mentioned but calculation needed
            if 'result' in [line for line in code_lines if 'data["result"]' in line]:
                # Result is already in the structure, but might need calculation
                calc_match = re.search(r"(\d+)\s*[+\-*/]\s*(\d+)", task_description)
                if calc_match and 'calc_result' not in '\n'.join(code_lines):
                    a, b = int(calc_match.group(1)), int(calc_match.group(2))
                    op_match = re.search(r"([+\-*/])", task_description)
                    op = op_match.group(1) if op_match else "+"
                    
                    # Insert calculation before result assignment
                    calc_lines = []
                    if op == "+":
                        calc_lines.append(f'calc_result = {a} + {b}')
                    elif op == "-":
                        calc_lines.append(f'calc_result = {a} - {b}')
                    elif op == "*":
                        calc_lines.append(f'calc_result = {a} * {b}')
                    elif op == "/":
                        calc_lines.append(f'calc_result = {a} / {b}')
                    else:
                        calc_lines.append(f'calc_result = {a} + {b}')
                    
                    # Find result line and replace with calculated value
                    new_lines = []
                    for line in code_lines:
                        if 'data["result"]' in line and not line.strip().startswith('#'):
                            # Replace static value with calculated result
                            new_lines.extend(calc_lines)
                            new_lines.append('data["result"] = calc_result')
                        else:
                            new_lines.append(line)
                    code_lines = new_lines
            
            return "\n".join(code_lines)
        
        # Pattern 2: Extract calculation result if mentioned
        calc_match = re.search(r"(\d+)\s*[+\-*/]\s*(\d+)", task_description)
        if calc_match:
            a, b = int(calc_match.group(1)), int(calc_match.group(2))
            op_match = re.search(r"([+\-*/])", task_description)
            op = op_match.group(1) if op_match else "+"
            
            code_lines.append(f'# Calculate result')
            if op == "+":
                code_lines.append(f'calc_result = {a} + {b}')
            elif op == "-":
                code_lines.append(f'calc_result = {a} - {b}')
            elif op == "*":
                code_lines.append(f'calc_result = {a} * {b}')
            elif op == "/":
                code_lines.append(f'calc_result = {a} / {b}')
            else:
                code_lines.append(f'calc_result = {a} + {b}')
            
            code_lines.append(f'data["calculation"] = "{a} {op} {b}"')
            code_lines.append(f'data["result"] = calc_result')
        
        # Extract step number
        step_match = re.search(r"step:\s*(\d+)", task_description, re.IGNORECASE)
        if step_match:
            code_lines.append(f'data["step"] = {int(step_match.group(1))}')
        
        # Extract message
        msg_match = re.search(r'message:\s*"([^"]+)"', task_description, re.IGNORECASE)
        if msg_match:
            code_lines.append(f'data["message"] = "{msg_match.group(1)}"')
        
        # If we have workflow-related fields
        if "workflow" in task_lower:
            workflow_match = re.search(r'workflow_id:\s*"([^"]+)"', task_description, re.IGNORECASE)
            if workflow_match:
                code_lines.append(f'data["workflow_id"] = "{workflow_match.group(1)}"')
            
            current_step_match = re.search(r'current_step:\s*(\d+)', task_description, re.IGNORECASE)
            if current_step_match:
                code_lines.append(f'data["current_step"] = {int(current_step_match.group(1))}')
            
            total_steps_match = re.search(r'total_steps:\s*(\d+)', task_description, re.IGNORECASE)
            if total_steps_match:
                code_lines.append(f'data["total_steps"] = {int(total_steps_match.group(1))}')
            
            if "results" in task_lower and "results:" in task_description:
                code_lines.append(f'data["results"] = []')
            
            if "status" in task_lower:
                status_match = re.search(r'status:\s*"([^"]+)"', task_description, re.IGNORECASE)
                if status_match:
                    code_lines.append(f'data["status"] = "{status_match.group(1)}"')
                elif "in_progress" in task_lower:
                    code_lines.append(f'data["status"] = "in_progress"')
                elif "completed" in task_lower:
                    code_lines.append(f'data["status"] = "completed"')
        
        # Return the code
        return "\n".join(code_lines)
    
    def _generate_json_update_code(self, task_description: str, task_lower: str, filename: str) -> str:
        """Generate code to update JSON file based on task description.
        
        Args:
            task_description: Task description
            task_lower: Lowercase version
            filename: JSON file path
            
        Returns:
            Python code to update the data dict
        """
        import re
        update_lines = []
        
        # Extract calculation and add to results array
        calc_match = re.search(r"(\d+)\s*[+\-*/]\s*(\d+)", task_description)
        if calc_match and "add" in task_lower and "result" in task_lower:
            a, b = int(calc_match.group(1)), int(calc_match.group(2))
            op_match = re.search(r"([+\-*/])", task_description)
            op = op_match.group(1) if op_match else "*"
            
            if op == "+":
                result = a + b
            elif op == "-":
                result = a - b
            elif op == "*":
                result = a * b
            elif op == "/":
                result = a / b
            else:
                result = a * b
            
            update_lines.append(f"# Calculate and add to results")
            update_lines.append(f"calc_result = {a} {op} {b}")
            update_lines.append(f'if "results" not in data:')
            update_lines.append(f'    data["results"] = []')
            update_lines.append(f'data["results"].append(calc_result)')
        
        # Update current_step
        step_match = re.search(r"current_step.*?(\d+)", task_description, re.IGNORECASE)
        if step_match:
            new_step = int(step_match.group(1))
            update_lines.append(f'data["current_step"] = {new_step}')
        
        # Update step number (for example 5) - look for "step to X" or "step: X" or "step field to X"
        step_num_match = re.search(r"step\s+(?:field\s+)?(?:to\s+)?(\d+)", task_description, re.IGNORECASE)
        if step_num_match:
            new_step = int(step_num_match.group(1))
            update_lines.append(f'data["step"] = {new_step}')
        
        # Update status
        if "completed" in task_lower:
            update_lines.append(f'data["status"] = "completed"')
        elif "in_progress" in task_lower:
            update_lines.append(f'data["status"] = "in_progress"')
        
        # Calculate total if mentioned
        if "total" in task_lower and "sum" in task_lower and "results" in task_lower:
            update_lines.append(f'# Calculate sum of results')
            update_lines.append(f'if "results" in data and isinstance(data["results"], list):')
            update_lines.append(f'    data["total"] = sum(data["results"])')
        
        # Handle "result + 1" or similar calculations
        if "result" in task_lower and ("+" in task_description or "-" in task_description or "*" in task_description or "/" in task_description):
            calc_match = re.search(r"result\s*([+\-*/])\s*(\d+)", task_description, re.IGNORECASE)
            if calc_match:
                op = calc_match.group(1)
                val = int(calc_match.group(2))
                if op == "+":
                    update_lines.append(f'if "result" in data:')
                    update_lines.append(f'    data["result"] = data["result"] + {val}')
                elif op == "-":
                    update_lines.append(f'if "result" in data:')
                    update_lines.append(f'    data["result"] = data["result"] - {val}')
                elif op == "*":
                    update_lines.append(f'if "result" in data:')
                    update_lines.append(f'    data["result"] = data["result"] * {val}')
                elif op == "/":
                    update_lines.append(f'if "result" in data:')
                    update_lines.append(f'    data["result"] = data["result"] / {val}')
        
        if not update_lines:
            return "    pass  # No updates needed"
        
        # Indent all lines for proper code structure
        indented_lines = ["    " + line if line.strip() and not line.strip().startswith("#") else "    " + line for line in update_lines]
        return "\n".join(indented_lines)
