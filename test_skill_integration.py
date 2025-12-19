"""
Integration test for AgentKernel skill management with sandbox execution.

This test verifies the complete skill workflow:
1. Save a skill using SkillManager
2. Execute code in the sandbox that imports the skill
3. Verify the skill runs correctly in the isolated environment

This ensures skills are properly accessible in the sandbox Python path.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from client.skill_manager import SkillManager
from client.sandbox_executor import SandboxExecutor
from config.schema import ExecutionConfig, GuardrailConfig, OptimizationConfig


def print_step(step: str, status: str = ""):
    """Print a test step."""
    if status == "✓":
        print(f"✓ {step}")
    elif status == "✗":
        print(f"✗ {step}")
    elif status == "⚠":
        print(f"⚠ {step}")
    else:
        print(f"  {step}")


def test_skill_sandbox_integration():
    """Test skill execution in sandbox."""
    print("=" * 60)
    print("AgentKernel Skill-Sandbox Integration Test")
    print("=" * 60)
    print()
    
    workspace_dir = "./workspace"
    
    try:
        # Test 1: Initialize components
        print("[Test 1] Initialize SkillManager and SandboxExecutor...")
        skill_manager = SkillManager(workspace_dir=workspace_dir)
        
        execution_config = ExecutionConfig(
            workspace_dir=workspace_dir,
            timeout=120.0,  # Increased timeout for first sandbox startup
        )
        guardrail_config = GuardrailConfig()
        optimization_config = OptimizationConfig()
        
        executor = SandboxExecutor(
            execution_config=execution_config,
            guardrail_config=guardrail_config,
            optimization_config=optimization_config,
        )
        
        print_step("SkillManager initialized", "✓")
        print_step("SandboxExecutor initialized", "✓")
        
        # Cleanup any existing skills from previous test runs
        existing_skills = skill_manager.list_skills()
        for skill in existing_skills:
            try:
                skill_manager.delete_skill(skill["name"])
                print_step(f"Cleaned up existing skill: {skill['name']}", "⚠")
            except:
                pass
        
        print()
        
        # Test 2: Save a simple skill
        print("[Test 2] Save a calculator skill...")
        calculator_code = '''
def add(a, b):
    """Add two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of a and b
    """
    return a + b

def multiply(a, b):
    """Multiply two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of a and b
    """
    return a * b

def factorial(n):
    """Calculate factorial of n.
    
    Args:
        n: Non-negative integer
        
    Returns:
        Factorial of n
    """
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''
        
        result = skill_manager.save_skill(
            name="calculator",
            code=calculator_code,
            description="Simple calculator functions for arithmetic operations",
            tags=["math", "arithmetic"]
        )
        
        assert result["status"] == "success", f"Save failed: {result}"
        print_step("Calculator skill saved", "✓")
        print_step(f"Path: {result['path']}", "✓")
        print()
        
        # Test 3: Execute code that imports the skill
        print("[Test 3] Execute code in sandbox that imports the skill...")
        test_code = '''
import sys
sys.path.insert(0, '/workspace')

from skills import calculator

# Test basic operations
result1 = calculator.add(5, 3)
result2 = calculator.multiply(4, 7)
result3 = calculator.factorial(5)

print(f"add(5, 3) = {result1}")
print(f"multiply(4, 7) = {result2}")
print(f"factorial(5) = {result3}")

# Verify results
assert result1 == 8, f"Expected 8, got {result1}"
assert result2 == 28, f"Expected 28, got {result2}"
assert result3 == 120, f"Expected 120, got {result3}"

print("All skill functions worked correctly!")
'''
        
        exec_result, output, error = executor.execute(test_code)
        
        if error:
            print(f"Execution error: {error}")
        assert exec_result == exec_result.SUCCESS, f"Execution failed: {error}"
        print_step("Code executed successfully in sandbox", "✓")
        print_step(f"Output: {output.strip() if output else ''}", "✓")
        print()
        
        # Test 4: Verify output contains expected results
        print("[Test 4] Verify skill execution results...")
        assert "add(5, 3) = 8" in output, "Addition result incorrect"
        assert "multiply(4, 7) = 28" in output, "Multiplication result incorrect"
        assert "factorial(5) = 120" in output, "Factorial result incorrect"
        assert "All skill functions worked correctly!" in output, "Assertion failed in sandbox"
        print_step("All calculations correct", "✓")
        print()
        
        # Test 5: Save another skill and test interaction
        print("[Test 5] Save a data processing skill...")
        data_processor_code = '''
def filter_even(numbers):
    """Filter even numbers from a list.
    
    Args:
        numbers: List of integers
        
    Returns:
        List of even numbers
    """
    return [n for n in numbers if n % 2 == 0]

def sum_list(numbers):
    """Sum all numbers in a list.
    
    Args:
        numbers: List of numbers
        
    Returns:
        Sum of all numbers
    """
    return sum(numbers)

def average(numbers):
    """Calculate average of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        Average value
    """
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)
'''
        
        result = skill_manager.save_skill(
            name="data_processor",
            code=data_processor_code,
            description="Data processing utilities for lists",
            tags=["data", "processing", "lists"]
        )
        
        assert result["status"] == "success"
        print_step("Data processor skill saved", "✓")
        print()
        
        # Test 6: Use both skills together
        print("[Test 6] Use multiple skills together in sandbox...")
        multi_skill_code = '''
import sys
sys.path.insert(0, '/workspace')

from skills import calculator, data_processor

# Generate some data
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Use data_processor to filter even numbers
evens = data_processor.filter_even(numbers)
print(f"Even numbers: {evens}")

# Use data_processor to calculate sum
total = data_processor.sum_list(evens)
print(f"Sum of evens: {total}")

# Use calculator to verify with factorial
fact_5 = calculator.factorial(5)
print(f"Factorial of 5: {fact_5}")

# Verify results
assert evens == [2, 4, 6, 8, 10], "Filter failed"
assert total == 30, "Sum failed"
assert fact_5 == 120, "Factorial failed"

print("Multiple skills working together successfully!")
'''
        
        exec_result, output, error = executor.execute(multi_skill_code)
        
        if error:
            print(f"Execution error: {error}")
        assert exec_result == exec_result.SUCCESS, f"Multi-skill execution failed: {error}"
        print_step("Multiple skills executed together", "✓")
        print_step(f"Output: {output.strip() if output else ''}", "✓")
        print()
        
        # Test 7: Test skill with error handling
        print("[Test 7] Test skill error handling...")
        error_handling_code = '''
import sys
sys.path.insert(0, '/workspace')

from skills import data_processor

# Test with empty list
result = data_processor.average([])
print(f"Average of empty list: {result}")
assert result == 0, "Empty list average should be 0"

# Test with normal data
result = data_processor.average([1, 2, 3, 4, 5])
print(f"Average of [1,2,3,4,5]: {result}")
assert result == 3.0, "Average calculation incorrect"

print("Error handling works correctly!")
'''
        
        exec_result, output, error = executor.execute(error_handling_code)
        
        if error:
            print(f"Execution error: {error}")
        assert exec_result == exec_result.SUCCESS, f"Error handling test failed: {error}"
        print_step("Skill error handling verified", "✓")
        print()
        
        # Test 8: Cleanup - delete one skill and verify it's no longer accessible
        print("[Test 8] Test skill deletion in sandbox context...")
        skill_manager.delete_skill("calculator")
        print_step("Deleted calculator skill", "✓")
        
        # Try to import deleted skill (should fail)
        import_deleted_code = '''
import sys
sys.path.insert(0, '/workspace')

try:
    from skills import calculator
    print("ERROR: Should not be able to import deleted skill")
    exit(1)
except ImportError as e:
    print(f"Correctly failed to import deleted skill: {e}")
    print("Deletion verification successful!")
'''
        
        exec_result, output, error = executor.execute(import_deleted_code)
        
        if error:
            print(f"Execution error: {error}")
        assert exec_result == exec_result.SUCCESS, "Deletion verification failed"
        assert "Deletion verification successful" in output
        print_step("Verified deleted skill not accessible", "✓")
        print()
        
        # Cleanup remaining skills
        skill_manager.delete_skill("data_processor")
        
        print("=" * 60)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  - Skill creation and save: ✓")
        print(f"  - Skill import in sandbox: ✓")
        print(f"  - Skill execution in sandbox: ✓")
        print(f"  - Multiple skills together: ✓")
        print(f"  - Error handling: ✓")
        print(f"  - Skill deletion verification: ✓")
        print()
        print("Skills are fully functional in the sandbox environment!")
        print()
        
        return True
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print("❌ INTEGRATION TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        return False
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ INTEGRATION TEST ERROR")
        print("=" * 60)
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_skill_sandbox_integration()
    sys.exit(0 if success else 1)
