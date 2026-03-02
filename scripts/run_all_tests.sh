#!/bin/bash
# Run all tests for code-execution-mcp

set -e

echo "=========================================="
echo "Running All Tests for Code Execution MCP"
echo "=========================================="
echo ""

cd "$(dirname "$0")"
source .venv/bin/activate

# Test 1: Volume Mount Test
echo "=== Test 1: Volume Mount Test ==="
echo ""
python test_volume_mount.py
echo ""
echo ""

# Test 2: Example 01 - Basic Tool Call
echo "=== Test 2: Example 01 - Basic Tool Call ==="
echo ""
python examples/01_basic_tool_call.py
echo ""
echo ""

# Test 3: Example 05 - State Persistence
echo "=== Test 3: Example 05 - State Persistence ==="
echo ""
python examples/05_state_persistence.py
echo ""
echo ""

# Check workspace files
echo "=== Workspace Files Check ==="
echo ""
echo "Python files in workspace:"
find workspace -type f -name "*.py" 2>/dev/null | head -20 || echo "No Python files found"
echo ""
echo "Workspace directory contents:"
ls -la workspace/ 2>/dev/null | head -20 || echo "Workspace directory not found or empty"
echo ""

echo "=========================================="
echo "All Tests Completed"
echo "=========================================="

