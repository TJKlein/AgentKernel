#!/usr/bin/env python3
"""Test script for MCP tool usage with Monty backend.

Adapted from test_mcp_tools.py to use Monty-compatible syntax (no 'with', use pathlib).
"""

import argparse
import json
import sys
import os
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agentkernel import create_agent

# Ensure we use Monty
os.environ["SANDBOX_TYPE"] = "monty"

class MCPToolTester:
    """Test MCP tools directly."""

    def __init__(self):
        """Initialize tester."""
        self.agent = None

    def setup(self):
        """Setup test environment."""
        print("✓ Using direct framework mode with Monty backend")
        self.agent = create_agent()

    def test_execute_task(self) -> bool:
        """Test execute_task tool."""
        print("\n" + "=" * 70)
        print("TEST: execute_task")
        print("=" * 70)

        try:
            result, output, error = self.agent.execute_task(
                "Calculate 5 + 3 and print the result",
                verbose=False
            )

            if error:
                print(f"❌ Error: {error}")
                return False

            if result.value != "success":
                print(f"❌ Execution failed: {result.value}")
                return False

            print(f"✅ Task executed successfully")
            print(f"   Result: {result.value}")
            if output:
                print(f"   Output: {str(output)[:100]}...")
            return True

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_list_available_tools(self) -> bool:
        """Test list_available_tools."""
        print("\n" + "=" * 70)
        print("TEST: list_available_tools")
        print("=" * 70)

        try:
            tools = self.agent.discover_tools(verbose=False)

            if not tools:
                print("❌ No tools discovered")
                return False

            print(f"✅ Discovered {sum(len(t) for t in tools.values())} tools from {len(tools)} servers")
            for server_name, tool_names in tools.items():
                print(f"   {server_name}: {len(tool_names)} tools")
                for tool_name in tool_names[:3]:  # Show first 3
                    print(f"     - {tool_name}")
                if len(tool_names) > 3:
                    print(f"     ... and {len(tool_names) - 3} more")

            return True

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_get_state(self) -> bool:
        """Test get_state tool."""
        print("\n" + "=" * 70)
        print("TEST: get_state")
        print("=" * 70)

        try:
            # First, save some state directly (bypassing guardrails for test setup)
            workspace_path = Path("./workspace")
            state_file = workspace_path / "test_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            test_data = {"test": "data", "value": 42}
            state_file.write_text(json.dumps(test_data, indent=2))

            # Now read it via code execution (simulating get_state)
            # ADAPTED FOR MONTY: use pathlib, no with
            result, output, error = self.agent.executor.execute(
                textwrap.dedent("""
                from pathlib import Path
                
                # Use helper json_loads provided by MontyExecutor
                p = Path('/workspace/test_state.json')
                content = p.read_text()
                data = json_loads(content)
                print(f"State data: {data}")
                """).strip()
            )

            if error:
                print(f"❌ Error: {error}")
                return False

            if result.value != "success":
                print(f"❌ Execution failed: {result.value}")
                return False

            # Verify file exists
            if not state_file.exists():
                print("❌ State file not found")
                return False

            print(f"✅ State retrieved successfully")
            print(f"   File: {state_file}")
            print(f"   Data: {test_data}")
            return True

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_save_state(self) -> bool:
        """Test save_state tool."""
        print("\n" + "=" * 70)
        print("TEST: save_state")
        print("=" * 70)

        try:
            test_data = {
                "test": "save_state",
                "timestamp": "2024-01-01T00:00:00Z",
                "value": 100
            }

            # Save state via code execution (simulating save_state)
            # ADAPTED FOR MONTY: use pathlib, no with
            result, output, error = self.agent.executor.execute(
                textwrap.dedent(f"""
                from pathlib import Path
                
                # Use helper json_dumps provided by MontyExecutor
                data = {json.dumps(test_data)}
                p = Path('/workspace/test_save_state.json')
                p.write_text(json_dumps(data, indent=2))
                print("State saved successfully")
                """).strip()
            )

            if error:
                print(f"❌ Error: {error}")
                return False

            if result.value != "success":
                print(f"❌ Execution failed: {result.value}")
                return False

            # Verify file exists
            workspace_path = Path("./workspace")
            state_file = workspace_path / "test_save_state.json"
            if not state_file.exists():
                print("❌ State file not created")
                return False

            # Verify content
            saved_data = json.loads(state_file.read_text())
            if saved_data != test_data:
                print(f"❌ Data mismatch")
                print(f"   Expected: {test_data}")
                print(f"   Got: {saved_data}")
                return False

            print(f"✅ State saved successfully")
            print(f"   File: {state_file}")
            print(f"   Data: {test_data}")
            return True

        except Exception as e:
            print(f"❌ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests."""
        self.setup()

        all_tests = {
            "execute_task": self.test_execute_task,
            "list_available_tools": self.test_list_available_tools,
            "get_state": self.test_get_state,
            "save_state": self.test_save_state,
            # Skipping server tests as they are same as original
        }

        results = {}
        for test_name, test_func in all_tests.items():
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"\n❌ Test '{test_name}' crashed: {e}")
                results[test_name] = False

        return results


def main():
    """Main entry point."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("MCP Tool Usage Test (Monty Backend)")
    print("=" * 70)
    print()

    tester = MCPToolTester()
    results = tester.run_all_tests()

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
