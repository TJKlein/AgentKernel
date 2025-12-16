# Examples Analysis: Hardcoding and Shortcuts

## Summary

**Issue Found:** The code generator has **hardcoded example calls** that don't adapt to the task description.

## Current Behavior

### What Works (No Hardcoding):
✅ **Tool Discovery** - Dynamically discovers tools from `servers/` directory
✅ **Tool Selection** - Uses semantic/keyword matching to select relevant tools
✅ **Mock Client** - Simulates real tool behavior (calculator actually calculates, weather returns realistic data)
✅ **Execution** - Code runs in real sandbox, produces real results

### What's Hardcoded (Shortcut):
❌ **Code Generation** - `_generate_smart_tool_call()` in `code_generator.py` has hardcoded example calls:

```python
# Hardcoded examples that ignore task description:
if tool_name == "add":
    return """result = add(5, 3)"""  # Always 5 + 3, regardless of task
elif tool_name == "get_weather":
    return """weather = get_weather(location="San Francisco, CA")"""  # Always SF
```

## Impact

**Example 1:** Task says "Calculate 5 + 3 and get weather for San Francisco"
- ✅ Correctly selects `calculate` and `get_weather` tools
- ❌ But generates hardcoded `calculate("5 + 3")` and `get_weather("San Francisco, CA")` 
- **Result:** Works by coincidence because hardcoded values match task

**Example 2:** Task says "Calculate 10 * 5, then get weather for that many cities starting with San Francisco"
- ✅ Correctly selects `calculate` and `get_forecast` tools  
- ❌ But generates hardcoded `multiply(4, 7)` and `get_forecast("San Francisco, CA", days=3)`
- **Result:** Doesn't match task - calculates wrong numbers, doesn't use result

**Example 3-7:** Similar issues - code generator ignores task-specific requirements

## Root Cause

The `_generate_smart_tool_call()` method in `code_generator.py` doesn't parse or use the `task_description` parameter. It just returns hardcoded example code for each tool.

## Solution Needed

The code generator should:
1. Parse the task description to extract:
   - Numbers to calculate
   - Locations for weather
   - File paths for filesystem operations
   - SQL queries for database operations
2. Generate code that matches the task requirements
3. Use extracted values instead of hardcoded examples

## Current Status

**Examples work, but only by coincidence** when hardcoded values happen to match the task. They don't truly adapt to different task descriptions.

**Mock client is fine** - it simulates real behavior (calculator performs math, weather returns realistic data). The issue is the code generation, not the mock implementation.




