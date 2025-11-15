"""Code generation utilities for creating tool usage code.

This module provides generic code generation capabilities that can be used
by any example or agent to generate Python code that uses discovered tools.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generic code generator for tool usage."""

    def __init__(self, include_error_handling: bool = True):
        """Initialize code generator.

        Args:
            include_error_handling: Whether to wrap tool calls in try-except blocks
        """
        self.include_error_handling = include_error_handling

    def generate_imports(self, required_tools: Dict[str, List[str]]) -> List[str]:
        """Generate import statements for required tools.

        Args:
            required_tools: Dict mapping server names to lists of tool names

        Returns:
            List of import statements
        """
        import_statements = []
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

    def generate_complete_code(
        self,
        required_tools: Dict[str, List[str]],
        task_description: str,
        task_specific_calls: Optional[Dict[str, List[str]]] = None,
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

        code = (
            header
            + "\n"
            + imports_str
            + "\n\n# Execute the task using selected tools\n"
            + usage_str
            + "\n"
        )

        return code
