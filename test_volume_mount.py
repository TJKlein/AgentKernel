#!/usr/bin/env python3
"""Test script to verify volume mounting is working."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from microsandbox import PythonSandbox


async def test_volume_mount():
    """Test that volume mounting works and files persist."""
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    print(f"📁 Workspace: {workspace}")
    print("🚀 Creating sandbox with volume mount...")
    
    try:
        async with PythonSandbox.create(
            name="test-volume-mount",
            volumes=[(str(workspace), "/workspace")]
        ) as sandbox:
            print("✅ Sandbox created")
            
            # Test 1: Verify /workspace exists and is accessible
            code1 = '''
import os
print("=== Test 1: Verify /workspace exists ===", flush=True)
print(f"/workspace exists: {os.path.exists('/workspace')}", flush=True)
print(f"/workspace is dir: {os.path.isdir('/workspace')}", flush=True)
if os.path.exists('/workspace'):
    contents = os.listdir('/workspace')
    print(f"/workspace contents: {contents}", flush=True)
'''
            result1 = await sandbox.run(code1)
            output1 = await result1.output()
            print("Output:")
            print(output1)
            
            # Test 2: Write a file
            code2 = '''
import os
print("=== Test 2: Write file to /workspace ===", flush=True)
test_content = "Hello from sandbox!"
with open('/workspace/test_volume.txt', 'w') as f:
    f.write(test_content)
print(f"✅ Written file with content: {test_content}", flush=True)
print(f"File exists: {os.path.exists('/workspace/test_volume.txt')}", flush=True)
if os.path.exists('/workspace/test_volume.txt'):
    with open('/workspace/test_volume.txt', 'r') as f:
        read_back = f.read()
    print(f"Read back: {read_back}", flush=True)
'''
            result2 = await sandbox.run(code2)
            output2 = await result2.output()
            print("Output:")
            print(output2)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify file exists on host
    print("\n=== Verifying file on host ===")
    test_file = workspace / "test_volume.txt"
    if test_file.exists():
        content = test_file.read_text()
        print(f"✅ SUCCESS! File found at {test_file}")
        print(f"   Content: {content}")
        if content == "Hello from sandbox!":
            print("✅ Content matches!")
            return True
        else:
            print(f"❌ Content mismatch. Expected 'Hello from sandbox!', got '{content}'")
            return False
    else:
        print(f"❌ FAILED - File not found at {test_file}")
        print(f"   Workspace contents: {list(workspace.iterdir())}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_volume_mount())
    sys.exit(0 if success else 1)

