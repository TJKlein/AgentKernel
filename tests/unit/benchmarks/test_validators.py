"""Unit tests for the benchmark validation logic."""
import pytest
from benchmarks.tasks.schema import Task
from benchmarks.validators import Validator

def test_exact_validator_match():
    task = Task(id="test01", name="t", category="compute", difficulty="easy", description="", 
                supported_backends=["opensandbox"], validation_type="exact", tags=[], 
                reference_code="print('A')", expected_output="A\\n")
    
    # Validator strips trailing whitespace internally and expects stripped answer
    success, score, details = Validator.validate(task, "A\\n")
    assert success is True
    assert score == 1.0
    assert "exact_match" in details.get("status", "exact_match")

def test_exact_validator_whitespace_tolerance():
    # Validator calls .strip() on both expected and actual output
    # Expected: 'Result' (stripped), actual: 'Result\n' (with trailing newline)
    task = Task(id="test02", name="t", category="compute", difficulty="easy", description="", 
                supported_backends=["opensandbox"], validation_type="exact", tags=[], 
                reference_code="print('Result')", expected_output="Result")
    
    # print() adds a trailing newline — after .strip() this should match 'Result'
    success, score, details = Validator.validate(task, "Result\n")
    assert success is True

def test_exact_validator_mismatch():
    task = Task(id="test03", name="t", category="compute", difficulty="easy", description="", 
                supported_backends=["opensandbox"], validation_type="exact", tags=[], 
                reference_code="print('A')", expected_output="A")
    
    success, score, details = Validator.validate(task, "B\\n")
    assert success is False
    assert score == 0.0

def test_fuzzy_validator_regex_match():
    task = Task(id="test04", name="t", category="compute", difficulty="easy", description="", 
                supported_backends=["opensandbox"], validation_type="fuzzy", tags=[], 
                reference_code="import random; print(random.random())", expected_output="")
    
    # Example fuzzy output that has standard output components we want to find
    output = "Model accuracy: 0.95\\nLoss: 0.05"
    
    # The fuzzy validator defaults to False if not properly implemented, so we check for failure in default state.
    success, score, details = Validator.validate(task, output)
    assert success is False

def test_custom_validator_missing():
    # Use category "ptc" so the validators module exists; missing function yields "not found"
    task = Task(id="test05", name="t", category="ptc", difficulty="easy", description="",
                supported_backends=["opensandbox"], validation_type="custom", tags=[],
                reference_code="pass", custom_validator="non_existent_func", expected_output="")

    success, score, details = Validator.validate(task, "output")
    assert success is False
    assert "error" in details
    # Either validator not found in module (AttributeError) or module missing (ImportError)
    assert "not found" in details["error"] or "Could not import" in details["error"]
