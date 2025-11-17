#!/usr/bin/env python3
"""Run all tests and save output to files."""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

def run_test(name, script_path):
    """Run a test script and save output."""
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}\n")
    
    output_file = Path(f"/tmp/test_{name.replace(' ', '_').lower()}.txt")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=Path(__file__).parent
        )
        
        # Save output
        with open(output_file, 'w') as f:
            f.write(f"=== {name} ===\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Return Code: {result.returncode}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n=== STDERR ===\n")
            f.write(result.stderr)
        
        # Print summary
        print(f"Return code: {result.returncode}")
        print(f"Output saved to: {output_file}")
        
        # Print key traces
        if "SETUP" in result.stdout or "VOLUME" in result.stdout or "Written" in result.stdout:
            print("\n=== Key Traces Found ===")
            lines = result.stdout.split('\n')
            for i, line in enumerate(lines):
                if any(kw in line for kw in ['SETUP', 'VOLUME', 'Written', 'ERROR', 'About to', 'Directory', 'Created', '✅', '❌']):
                    print(f"Line {i+1}: {line}")
        
        # Print last 20 lines
        print("\n=== Last 20 lines of output ===")
        for line in result.stdout.split('\n')[-20:]:
            if line.strip():
                print(line)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"❌ {name} timed out after 180 seconds")
        return False
    except Exception as e:
        print(f"❌ Error running {name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    base_path = Path(__file__).parent
    
    tests = [
        ("Simple Test", base_path / "simple_test.py"),
        ("Volume Mount Test", base_path / "test_volume_mount.py"),
        ("Example 01 - Basic Tool Call", base_path / "examples" / "01_basic_tool_call.py"),
        ("Example 05 - State Persistence", base_path / "examples" / "05_state_persistence.py"),
    ]
    
    results = {}
    
    for name, script_path in tests:
        if script_path.exists():
            results[name] = run_test(name, script_path)
        else:
            print(f"⚠️  {name}: Script not found at {script_path}")
            results[name] = None
    
    # Check workspace files
    print(f"\n{'='*60}")
    print("Workspace Files Check")
    print(f"{'='*60}\n")
    
    workspace = base_path / "workspace"
    if workspace.exists():
        print(f"Workspace exists: {workspace}")
        print(f"Contents: {list(workspace.iterdir())}")
        
        # Check for Python files
        py_files = list(workspace.rglob("*.py"))
        if py_files:
            print(f"\nPython files found: {len(py_files)}")
            for py_file in py_files[:20]:
                print(f"  {py_file.relative_to(workspace)}")
        else:
            print("\nNo Python files found in workspace")
        
        # Check for client and servers directories
        client_dir = workspace / "client"
        servers_dir = workspace / "servers"
        
        if client_dir.exists():
            print(f"\n✅ client/ directory exists")
            print(f"   Contents: {list(client_dir.iterdir())}")
        else:
            print(f"\n❌ client/ directory not found")
        
        if servers_dir.exists():
            print(f"\n✅ servers/ directory exists")
            for server in servers_dir.iterdir():
                if server.is_dir():
                    files = list(server.glob("*.py"))
                    print(f"   {server.name}: {len(files)} Python files")
        else:
            print(f"\n❌ servers/ directory not found")
    else:
        print("❌ Workspace directory not found")
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}\n")
    
    for name, result in results.items():
        if result is True:
            print(f"✅ {name}: PASSED")
        elif result is False:
            print(f"❌ {name}: FAILED")
        else:
            print(f"⚠️  {name}: NOT RUN")
    
    print(f"\nAll output files saved to /tmp/test_*.txt")

if __name__ == "__main__":
    main()

