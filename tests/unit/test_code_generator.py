import pytest
from client.code_generator import CodeGenerator

def test_generate_imports_valid():
    """Test generating imports for valid tools."""
    gen = CodeGenerator(llm_config=None)
    required_tools = {"calculator": ["add", "multiply"]}
    imports = gen.generate_imports(required_tools)
    assert len(imports) == 1
    assert "from servers.calculator import add, multiply" in imports[0]

def test_generate_imports_none():
    """Test generating imports with None required_tools (Regression fix)."""
    gen = CodeGenerator(llm_config=None)
    imports = gen.generate_imports(None)
    assert imports == []

def test_generate_imports_empty():
    """Test generating imports with empty dict."""
    gen = CodeGenerator(llm_config=None)
    imports = gen.generate_imports({})
    assert imports == []

def test_generate_usage_code_none():
    """Test generating usage code with None required_tools (Regression fix)."""
    gen = CodeGenerator(llm_config=None)
    usage = gen.generate_usage_code(None, "Task")
    assert usage == []

def test_generate_usage_code_valid():
    """Test generating usage code for known tools."""
    gen = CodeGenerator(llm_config=None)
    required_tools = {"calculator": ["add"]}
    usage = gen.generate_usage_code(required_tools, "Calculate 5 + 3")
    assert len(usage) == 1
    assert "result = add(5, 3)" in usage[0]
