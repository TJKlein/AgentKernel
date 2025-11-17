#!/usr/bin/env python3
"""Simple test to verify sandbox execution and volume mounting."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("Simple Sandbox Test")
print("=" * 60)
print()

try:
    from microsandbox import PythonSandbox
    print("✅ microsandbox imported successfully")
except ImportError as e:
    print(f"❌ Failed to import microsandbox: {e}")
    sys.exit(1)

async def test():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    print(f"📁 Workspace: {workspace}")
    print("🚀 Creating sandbox...")
    
    try:
        async with PythonSandbox.create(
            name="simple-test",
            volumes=[(str(workspace), "/workspace")]
        ) as sandbox:
            print("✅ Sandbox created")
            
            # Simple test code
            code = '''
import os
import sys

print("=== Test Code Running ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"/workspace exists: {os.path.exists('/workspace')}", flush=True)

if os.path.exists('/workspace'):
    print(f"/workspace is dir: {os.path.isdir('/workspace')}", flush=True)
    try:
        contents = os.listdir('/workspace')
        print(f"/workspace contents: {contents}", flush=True)
    except Exception as e:
        print(f"Error listing /workspace: {e}", flush=True)
    
    # Try to write a file
    try:
        test_file = '/workspace/simple_test_output.txt'
        with open(test_file, 'w') as f:
            f.write('Test successful!')
        print(f"✅ Written {test_file}", flush=True)
        print(f"File exists: {os.path.exists(test_file)}", flush=True)
    except Exception as e:
        print(f"❌ Error writing file: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
'''
            
            print("📝 Running test code...")
            result = await sandbox.run(code)
            output = await result.output()
            
            print("\n=== Sandbox Output ===")
            print(output)
            print()
            
            # Check stderr too
            try:
                stderr = await result.error()
                if stderr:
                    print("=== Stderr Output ===")
                    print(stderr)
                    print()
            except:
                pass
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Check if file was created
    print("=== Checking Host Filesystem ===")
    test_file = workspace / "simple_test_output.txt"
    if test_file.exists():
        content = test_file.read_text()
        print(f"✅ File found: {test_file}")
        print(f"   Content: {content}")
        return True
    else:
        print(f"❌ File not found: {test_file}")
        print(f"   Workspace contents: {list(workspace.iterdir())}")
        return False

if __name__ == "__main__":
    print("Starting test...")
    print()
    success = asyncio.run(test())
    print()
    print("=" * 60)
    if success:
        print("✅ TEST PASSED")
    else:
        print("❌ TEST FAILED")
    print("=" * 60)
    sys.exit(0 if success else 1)

