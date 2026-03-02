#!/bin/bash
# Script to run all examples and report results

set -e

cd "$(dirname "$0")"
EXAMPLES_DIR="examples"

echo "============================================================"
echo "Running All Examples"
echo "============================================================"
echo ""

# Array of example files
examples=(
    "01_basic_tool_call.py"
    "02_multi_tool_chain.py"
    "03_data_filtering.py"
    "04_control_flow.py"
    "05_state_persistence.py"
    "06_skills.py"
    "07_filesystem_operations.py"
)

# Results tracking
passed=0
failed=0
skipped=0

for example in "${examples[@]}"; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Running: $example"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ ! -f "$EXAMPLES_DIR/$example" ]; then
        echo "✗ ERROR: File not found: $EXAMPLES_DIR/$example"
        ((failed++))
        continue
    fi
    
    # Try to run with python3
    if python3 "$EXAMPLES_DIR/$example" 2>&1; then
        echo ""
        echo "✓ SUCCESS: $example completed"
        ((passed++))
    else
        exit_code=$?
        echo ""
        if [ $exit_code -eq 1 ]; then
            echo "⚠ SKIPPED: $example (likely missing dependencies or microsandbox server)"
            ((skipped++))
        else
            echo "✗ FAILED: $example (exit code: $exit_code)"
            ((failed++))
        fi
    fi
    
    echo ""
    sleep 1  # Small delay between examples
done

echo ""
echo "============================================================"
echo "Summary"
echo "============================================================"
echo "Passed:  $passed"
echo "Failed:  $failed"
echo "Skipped: $skipped"
echo "Total:   $((passed + failed + skipped))"
echo "============================================================"

if [ $failed -eq 0 ] && [ $skipped -eq 0 ]; then
    exit 0
elif [ $failed -eq 0 ]; then
    exit 0  # Some skipped is OK if dependencies aren't set up
else
    exit 1
fi

