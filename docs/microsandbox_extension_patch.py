"""
Example patch showing how to extend microsandbox Python API for volume support.

This is a reference implementation showing the changes needed.
To actually use this, you would need to:
1. Fork the microsandbox repository
2. Apply these changes
3. Install from your fork

Usage after extension:
    from pathlib import Path
    from microsandbox import PythonSandbox

    workspace_path = Path("./workspace").resolve()

    async with PythonSandbox.create(
        name="code-execution",
        volumes=[(str(workspace_path), "/workspace")]
    ) as sandbox:
        exec_result = await sandbox.run(code)
"""

from typing import List, Tuple, Optional
from pathlib import Path

# ============================================================================
# PATCH 1: base_sandbox.py - Add volumes to __init__ and start()
# ============================================================================

PATCH_BASE_SANDBOX_INIT = """
# In BaseSandbox.__init__(), add:
self._volumes: Optional[List[Tuple[str, str]]] = None
"""

PATCH_BASE_SANDBOX_CREATE = """
# In BaseSandbox.create(), change signature to:
@classmethod
@asynccontextmanager
async def create(
    cls,
    server_url: str = None,
    namespace: str = "default",
    name: Optional[str] = None,
    api_key: Optional[str] = None,
    volumes: Optional[List[Tuple[str, str]]] = None,  # NEW PARAMETER
):
    # ... existing code ...
    
    sandbox = cls(
        server_url=server_url,
        namespace=namespace,
        name=name,
        api_key=api_key,
    )
    
    try:
        sandbox._session = aiohttp.ClientSession()
        await sandbox.start(volumes=volumes)  # Pass volumes here
        yield sandbox
    finally:
        await sandbox.stop()
        if sandbox._session:
            await sandbox._session.close()
            sandbox._session = None
"""

PATCH_BASE_SANDBOX_START = """
# In BaseSandbox.start(), change signature and add volumes to config:
async def start(
    self,
    image: Optional[str] = None,
    memory: int = 512,
    cpus: float = 1.0,
    timeout: float = 180.0,
    volumes: Optional[List[Tuple[str, str]]] = None,  # NEW PARAMETER
) -> None:
    if self._is_started:
        return

    sandbox_image = image or await self.get_default_image()
    
    # Build config
    config = {
        "image": sandbox_image,
        "memory": memory,
        "cpus": int(cpus),
    }
    
    # ADD THIS: Include volumes in config
    if volumes:
        config["volumes"] = [
            {
                "host": str(Path(host_path).resolve()),  # Resolve to absolute path
                "mount": mount_path
            }
            for host_path, mount_path in volumes
        ]
    
    request_data = {
        "jsonrpc": "2.0",
        "method": "sandbox.start",
        "params": {
            "namespace": self._namespace,
            "sandbox": self._name,
            "config": config,  # Config now includes volumes
        },
        "id": str(uuid.uuid4()),
    }
    
    # ... rest of existing start() implementation ...
"""

# ============================================================================
# PATCH 2: Rust core - Handle volumes in JSON-RPC handler
# ============================================================================

PATCH_RUST_HANDLER = """
// In the sandbox.start JSON-RPC handler (likely in a handler.rs file)

// Parse volumes from config
if let Some(volumes_value) = config.get("volumes") {
    if let Some(volumes_array) = volumes_value.as_array() {
        let mut volume_pairs = Vec::new();
        
        for vol in volumes_array {
            if let (Some(host), Some(mount)) = (
                vol.get("host").and_then(|v| v.as_str()),
                vol.get("mount").and_then(|v| v.as_str()),
            ) {
                volume_pairs.push((
                    host.to_string(),
                    mount.to_string(),
                ));
            }
        }
        
        // Add volumes to sandbox config
        // This will be used by patch_with_virtiofs_mounts
        sandbox_config.volumes = volume_pairs;
    }
}
"""

# ============================================================================
# COMPLETE EXAMPLE: How it would look after extension
# ============================================================================

EXAMPLE_USAGE = """
# After extension, usage in client/sandbox_executor.py:

from pathlib import Path
from microsandbox import PythonSandbox

workspace_path = Path("./workspace").resolve()

async with PythonSandbox.create(
    name="code-execution",
    volumes=[(str(workspace_path), "/workspace")]  # Mount workspace directory
) as sandbox:
    # Files written to /workspace in sandbox are now persisted to host
    exec_result = await sandbox.run(code)
    output = await exec_result.output()
    
    # State written to /workspace/result.txt in sandbox
    # is automatically available at ./workspace/result.txt on host
"""

# ============================================================================
# TEST EXAMPLE
# ============================================================================

TEST_EXAMPLE = """
# Test script to verify volume mounting works:

import asyncio
from pathlib import Path
from microsandbox import PythonSandbox

async def test_volume_mount():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    # Create sandbox with workspace mounted
    async with PythonSandbox.create(
        name="test-volumes",
        volumes=[(str(workspace), "/workspace")]
    ) as sandbox:
        # Write file in sandbox
        code = '''
import os
os.makedirs("/workspace", exist_ok=True)
with open("/workspace/test.txt", "w") as f:
    f.write("Hello from sandbox!")
print("File written to /workspace/test.txt")
'''
        exec_result = await sandbox.run(code)
        print(await exec_result.output())
    
    # Verify file exists on host
    test_file = workspace / "test.txt"
    if test_file.exists():
        print(f"✅ Volume mount works! File found at {test_file}")
        print(f"   Content: {test_file.read_text()}")
    else:
        print("❌ Volume mount failed - file not found on host")

if __name__ == "__main__":
    asyncio.run(test_volume_mount())
"""

if __name__ == "__main__":
    print("=" * 70)
    print("MICROSANDBOX VOLUME EXTENSION PATCH")
    print("=" * 70)
    print("\n1. BASE_SANDBOX.PY CHANGES:")
    print("-" * 70)
    print(PATCH_BASE_SANDBOX_INIT)
    print(PATCH_BASE_SANDBOX_CREATE)
    print(PATCH_BASE_SANDBOX_START)
    print("\n2. RUST CORE CHANGES:")
    print("-" * 70)
    print(PATCH_RUST_HANDLER)
    print("\n3. USAGE EXAMPLE:")
    print("-" * 70)
    print(EXAMPLE_USAGE)
    print("\n4. TEST EXAMPLE:")
    print("-" * 70)
    print(TEST_EXAMPLE)
