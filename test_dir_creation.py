#!/usr/bin/env python3
"""Minimal test for directory creation in sandbox."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from microsandbox import PythonSandbox

async def test():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    print("=== Testing Directory Creation ===")
    
    code = """
import os
import sys

print('=== START ===', flush=True)
print(f'Python: {sys.version}', flush=True)
print(f'CWD: {os.getcwd()}', flush=True)
print(f'/workspace exists: {os.path.exists("/workspace")}', flush=True)
print('', flush=True)

print('=== Creating directories ===', flush=True)

print('1. Creating /workspace/servers...', flush=True)
try:
    os.makedirs('/workspace/servers', exist_ok=True)
    exists = os.path.exists('/workspace/servers')
    isdir = os.path.isdir('/workspace/servers')
    print(f'   ✅ /workspace/servers: exists={exists}, isdir={isdir}', flush=True)
except Exception as e:
    print(f'   ❌ Error: {type(e).__name__}: {e}', flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)

print('2. Creating /workspace/client...', flush=True)
try:
    os.makedirs('/workspace/client', exist_ok=True)
    exists = os.path.exists('/workspace/client')
    isdir = os.path.isdir('/workspace/client')
    print(f'   ✅ /workspace/client: exists={exists}, isdir={isdir}', flush=True)
except Exception as e:
    print(f'   ❌ Error: {type(e).__name__}: {e}', flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)

print('3. Creating /workspace/skills...', flush=True)
try:
    os.makedirs('/workspace/skills', exist_ok=True)
    exists = os.path.exists('/workspace/skills')
    isdir = os.path.isdir('/workspace/skills')
    print(f'   ✅ /workspace/skills: exists={exists}, isdir={isdir}', flush=True)
except Exception as e:
    print(f'   ❌ Error: {type(e).__name__}: {e}', flush=True)
    import traceback
    traceback.print_exc(file=sys.stdout)

print('', flush=True)
print('=== Verification ===', flush=True)
for dir_path in ['/workspace/servers', '/workspace/client', '/workspace/skills']:
    exists = os.path.exists(dir_path)
    isdir = os.path.isdir(dir_path) if exists else False
    print(f'{dir_path}: exists={exists}, isdir={isdir}', flush=True)

print('=== END ===', flush=True)
"""
    
    async with PythonSandbox.create(
        name="test-dir-creation",
        volumes=[(str(workspace), "/workspace")]
    ) as sandbox:
        result = await sandbox.run(code)
        output = await result.output()
        print("\n=== Sandbox Output ===")
        print(output)
        
        try:
            stderr = await result.error()
            if stderr:
                print("\n=== Stderr ===")
                print(stderr)
        except:
            pass
    
    print("\n=== Host Filesystem Check ===")
    for dir_name in ['servers', 'client', 'skills']:
        dir_path = workspace / dir_name
        print(f"{dir_name}/: exists={dir_path.exists()}, is_dir={dir_path.is_dir() if dir_path.exists() else False}")

if __name__ == "__main__":
    asyncio.run(test())

