#!/usr/bin/env python3
"""Run all examples and verify they work correctly."""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# List of examples to run
EXAMPLES = [
    ("01_basic_tool_call.py", "Basic Tool Call"),
    ("02_multi_tool_chain.py", "Multi-Tool Chain"),
    ("03_data_filtering.py", "Data Filtering"),
    ("04_control_flow.py", "Control Flow"),
    ("05_state_persistence.py", "State Persistence"),
    ("06_skills.py", "Skills"),
    ("07_filesystem_operations.py", "Filesystem Operations"),
    ("08_cross_session_persistence.py", "Cross-Session Persistence"),
]

def run_example(example_file: str, example_name: str) -> tuple[bool, float]:
    """Run a single example and return (success, duration)."""
    print(f"\n{'=' * 70}")
    print(f"Running: {example_name} ({example_file})")
    print(f"{'=' * 70}")
    
    start_time = time.time()
    
    try:
        import subprocess
        # Try to use venv python if available
        venv_python = project_root / ".venv" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else sys.executable
        
        result = subprocess.run(
            [python_cmd, str(project_root / "examples" / example_file)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per example
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {example_name} completed successfully in {duration:.2f}s")
            if result.stdout:
                # Show last 20 lines of output
                lines = result.stdout.strip().split('\n')
                if len(lines) > 20:
                    print("\n... (output truncated) ...")
                    for line in lines[-20:]:
                        print(line)
                else:
                    print(result.stdout)
            return True, duration
        else:
            print(f"❌ {example_name} failed after {duration:.2f}s")
            print(f"Return code: {result.returncode}")
            if result.stdout:
                print("\nSTDOUT:")
                print(result.stdout[-1000:])  # Last 1000 chars
            if result.stderr:
                print("\nSTDERR:")
                print(result.stderr[-1000:])  # Last 1000 chars
            return False, duration
            
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"⏱️ {example_name} timed out after {duration:.2f}s")
        return False, duration
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ {example_name} raised exception: {e}")
        return False, duration


def main():
    """Run all examples and report results."""
    print("=" * 70)
    print("Running All Examples")
    print("=" * 70)
    
    results = []
    total_start = time.time()
    
    for example_file, example_name in EXAMPLES:
        success, duration = run_example(example_file, example_name)
        results.append((example_name, success, duration))
    
    total_duration = time.time() - total_start
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful
    
    for example_name, success, duration in results:
        status = "✅" if success else "❌"
        print(f"{status} {example_name:40s} {duration:6.2f}s")
    
    print("-" * 70)
    print(f"Total: {len(results)} examples, {successful} successful, {failed} failed")
    print(f"Total time: {total_duration:.2f}s")
    print(f"Average time per example: {total_duration/len(results):.2f}s")
    
    if failed > 0:
        print("\n❌ Some examples failed!")
        sys.exit(1)
    else:
        print("\n✅ All examples passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

