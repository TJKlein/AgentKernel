"""Mock MCP client for testing and examples without real MCP servers."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)

# Mock data storage
_mock_files: Dict[str, str] = {}
_mock_directories: Dict[str, list] = {}
_mock_database_tables: Dict[str, list] = {}


def _mock_calculator_add(a: float, b: float) -> float:
    """Mock implementation of calculator add."""
    return a + b


def _mock_calculator_multiply(a: float, b: float) -> float:
    """Mock implementation of calculator multiply."""
    return a * b


def _mock_calculator_calculate(expression: str) -> float:
    """Mock implementation of calculator calculate."""
    # Safe mock implementation without eval()
    # For demo purposes, we'll do simple arithmetic parsing
    try:
        # Remove whitespace
        expr = expression.replace(" ", "")

        # Very simple parser for basic arithmetic (no eval)
        # This is a simplified version - in production use a proper parser
        if "+" in expr:
            parts = expr.split("+", 1)
            return float(parts[0]) + float(parts[1])
        elif "-" in expr and not expr.startswith("-"):
            parts = expr.split("-", 1)
            return float(parts[0]) - float(parts[1])
        elif "*" in expr:
            parts = expr.split("*", 1)
            return float(parts[0]) * float(parts[1])
        elif "/" in expr:
            parts = expr.split("/", 1)
            return float(parts[0]) / float(parts[1])
        else:
            # If no operator, just return the number
            return float(expr)
    except Exception as e:
        # Fallback: return a mock result based on expression length
        return float(len(expression) * 2.5)


def _mock_weather_get_weather(location: str, units: Optional[str] = None) -> Dict[str, Any]:
    """Mock implementation of weather get_weather."""
    temp_unit = units or "celsius"
    base_temp = random.randint(15, 30) if temp_unit == "celsius" else random.randint(59, 86)

    conditions = ["sunny", "cloudy", "partly cloudy", "rainy", "windy"]

    return {
        "location": location,
        "temperature": base_temp,
        "unit": temp_unit,
        "condition": random.choice(conditions),
        "humidity": random.randint(40, 80),
        "wind_speed": random.randint(5, 25),
        "timestamp": datetime.now().isoformat(),
    }


def _mock_weather_get_forecast(
    location: str, days: Optional[int] = None, units: Optional[str] = None
) -> Dict[str, Any]:
    """Mock implementation of weather get_forecast."""
    days = days or 5
    temp_unit = units or "celsius"
    base_temp = random.randint(15, 30) if temp_unit == "celsius" else random.randint(59, 86)

    conditions = ["sunny", "cloudy", "partly cloudy", "rainy", "windy"]
    forecast = []

    for i in range(days):
        date = datetime.now() + timedelta(days=i)
        forecast.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "high": base_temp + random.randint(-5, 5),
                "low": base_temp - random.randint(5, 10),
                "condition": random.choice(conditions),
                "precipitation_chance": random.randint(0, 50),
            }
        )

    return {
        "location": location,
        "unit": temp_unit,
        "forecast": forecast,
    }


def _mock_filesystem_read_file(path: str, encoding: Optional[str] = None) -> str:
    """Mock implementation of filesystem read_file."""
    if path in _mock_files:
        return _mock_files[path]
    else:
        raise FileNotFoundError(f"File not found: {path}")


def _mock_filesystem_write_file(
    path: str, content: str, encoding: Optional[str] = None
) -> Dict[str, Any]:
    """Mock implementation of filesystem write_file."""
    _mock_files[path] = content
    return {
        "path": path,
        "bytes_written": len(content.encode(encoding or "utf-8")),
        "success": True,
    }


def _mock_filesystem_list_directory(path: str, recursive: Optional[bool] = None) -> Dict[str, Any]:
    """Mock implementation of filesystem list_directory."""
    recursive = recursive or False

    if path in _mock_directories:
        items = _mock_directories[path]
    else:
        # Generate some default mock files/directories
        items = [
            {"name": "file1.txt", "type": "file", "size": 1024},
            {"name": "file2.py", "type": "file", "size": 2048},
            {"name": "subdir", "type": "directory"},
        ]
        _mock_directories[path] = items

    return {
        "path": path,
        "items": items,
        "recursive": recursive,
    }


def _mock_database_query(sql: str, parameters: Optional[list] = None) -> list:
    """Mock implementation of database query."""
    # Simple mock that returns sample data based on SQL
    sql_lower = sql.lower().strip()

    if "select" in sql_lower:
        # Return mock query results
        if "users" in sql_lower:
            return [
                {"id": 1, "name": "Alice", "email": "alice@example.com"},
                {"id": 2, "name": "Bob", "email": "bob@example.com"},
                {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
            ]
        elif "products" in sql_lower:
            return [
                {"id": 1, "name": "Product A", "price": 29.99},
                {"id": 2, "name": "Product B", "price": 49.99},
            ]
        else:
            return [{"result": "mock_data", "count": 3}]
    else:
        return []


def _mock_database_execute(sql: str, parameters: Optional[list] = None) -> Dict[str, Any]:
    """Mock implementation of database execute."""
    sql_lower = sql.lower().strip()

    if "insert" in sql_lower:
        return {"rows_affected": 1, "last_insert_id": random.randint(100, 999)}
    elif "update" in sql_lower:
        return {"rows_affected": random.randint(1, 10)}
    elif "delete" in sql_lower:
        return {"rows_affected": random.randint(1, 5)}
    else:
        return {"rows_affected": 0}


def _mock_database_list_tables() -> list:
    """Mock implementation of database list_tables."""
    if not _mock_database_tables:
        _mock_database_tables["users"] = []
        _mock_database_tables["products"] = []
        _mock_database_tables["orders"] = []

    return list(_mock_database_tables.keys())


# Mapping of server_name -> tool_name -> handler function
_MOCK_HANDLERS: Dict[str, Dict[str, Any]] = {
    "calculator": {
        "add": _mock_calculator_add,
        "multiply": _mock_calculator_multiply,
        "calculate": _mock_calculator_calculate,
    },
    "weather": {
        "get_weather": _mock_weather_get_weather,
        "get_forecast": _mock_weather_get_forecast,
    },
    "filesystem": {
        "read_file": _mock_filesystem_read_file,
        "write_file": _mock_filesystem_write_file,
        "list_directory": _mock_filesystem_list_directory,
    },
    "database": {
        "query": _mock_database_query,
        "execute": _mock_database_execute,
        "list_tables": _mock_database_list_tables,
    },
}


def call_mcp_tool(
    server_name: str,
    tool_name: str,
    parameters: Dict[str, Any],
    server_configs: Optional[list] = None,
) -> Any:
    """Mock implementation of call_mcp_tool that returns mock data."""
    logger.info(f"Mock MCP tool call: {server_name}.{tool_name}({parameters})")

    if server_name not in _MOCK_HANDLERS:
        raise ValueError(
            f"Mock server '{server_name}' not found. Available: {list(_MOCK_HANDLERS.keys())}"
        )

    if tool_name not in _MOCK_HANDLERS[server_name]:
        raise ValueError(
            f"Mock tool '{tool_name}' not found in server '{server_name}'. "
            f"Available: {list(_MOCK_HANDLERS[server_name].keys())}"
        )

    handler = _MOCK_HANDLERS[server_name][tool_name]

    try:
        # Call the handler with unpacked parameters
        result = handler(**parameters)
        logger.info(f"Mock MCP tool result: {result}")
        return result
    except Exception as e:
        logger.error(f"Mock MCP tool call failed: {e}")
        raise


def reset_mock_data() -> None:
    """Reset all mock data storage."""
    global _mock_files, _mock_directories, _mock_database_tables
    _mock_files.clear()
    _mock_directories.clear()
    _mock_database_tables.clear()
    logger.info("Mock data reset")
