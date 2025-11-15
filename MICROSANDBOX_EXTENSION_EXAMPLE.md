# Microsandbox Volume Mount Extension Example

This document shows how to extend the microsandbox Python API to support volume mounts, enabling full workspace persistence as described in the Anthropic article.

## Current Implementation

The microsandbox Rust core already supports volumes via `patch_with_virtiofs_mounts` (see [sandbox.rs:636](https://raw.githubusercontent.com/zerocore-ai/microsandbox/0d99770d6d0da1046dec8d1e0fc7da3bf4dee407/microsandbox-core/lib/management/sandbox.rs#L636)), but the Python API doesn't expose this.

## Extension Required

### 1. Modify `base_sandbox.py`

**Current `start()` method signature:**
```python
async def start(
    self,
    image: Optional[str] = None,
    memory: int = 512,
    cpus: float = 1.0,
    timeout: float = 180.0,
) -> None:
```

**Extended version with volumes:**
```python
async def start(
    self,
    image: Optional[str] = None,
    memory: int = 512,
    cpus: float = 1.0,
    timeout: float = 180.0,
    volumes: Optional[List[Tuple[str, str]]] = None,  # NEW: [(host_path, mount_path), ...]
) -> None:
    """
    Start the sandbox container.

    Args:
        image: Docker image to use for the sandbox
        memory: Memory limit in MB
        cpus: CPU limit
        timeout: Maximum time in seconds to wait for the sandbox to start
        volumes: List of (host_path, mount_path) tuples for volume mounts
                 Example: [("/host/workspace", "/workspace")]
    """
    if self._is_started:
        return

    sandbox_image = image or await self.get_default_image()
    
    # Build config with volumes
    config = {
        "image": sandbox_image,
        "memory": memory,
        "cpus": int(cpus),
    }
    
    # Add volumes if provided
    if volumes:
        config["volumes"] = [
            {"host": host_path, "mount": mount_path}
            for host_path, mount_path in volumes
        ]
    
    request_data = {
        "jsonrpc": "2.0",
        "method": "sandbox.start",
        "params": {
            "namespace": self._namespace,
            "sandbox": self._name,
            "config": config,  # Now includes volumes
        },
        "id": str(uuid.uuid4()),
    }
    
    # ... rest of start() implementation
```

### 2. Modify `create()` classmethod

**Current `create()` signature:**
```python
@classmethod
@asynccontextmanager
async def create(
    cls,
    server_url: str = None,
    namespace: str = "default",
    name: Optional[str] = None,
    api_key: Optional[str] = None,
):
```

**Extended version:**
```python
@classmethod
@asynccontextmanager
async def create(
    cls,
    server_url: str = None,
    namespace: str = "default",
    name: Optional[str] = None,
    api_key: Optional[str] = None,
    volumes: Optional[List[Tuple[str, str]]] = None,  # NEW
):
    """
    Create and initialize a new sandbox as an async context manager.

    Args:
        server_url: URL of the Microsandbox server
        namespace: Namespace for the sandbox
        name: Optional name for the sandbox
        api_key: API key for authentication
        volumes: List of (host_path, mount_path) tuples for volume mounts
                 Example: [("/host/workspace", "/workspace")]
    """
    # ... existing initialization code ...
    
    sandbox = cls(
        server_url=server_url,
        namespace=namespace,
        name=name,
        api_key=api_key,
    )
    
    # Store volumes for use in start()
    sandbox._volumes = volumes or []
    
    try:
        sandbox._session = aiohttp.ClientSession()
        # Pass volumes to start()
        await sandbox.start(volumes=volumes)
        yield sandbox
    finally:
        await sandbox.stop()
        if sandbox._session:
            await sandbox._session.close()
            sandbox._session = None
```

### 3. Update Rust Core API Handler

The Rust core needs to handle the `volumes` field in the JSON-RPC request. The `sandbox.start` handler should:

1. Parse the `volumes` array from the config
2. Convert to the format expected by `patch_with_virtiofs_mounts`
3. Pass to the sandbox setup function

**Rust handler example (pseudo-code):**
```rust
// In the sandbox.start JSON-RPC handler
if let Some(volumes) = config.get("volumes") {
    let volume_pairs: Vec<(String, String)> = volumes
        .as_array()
        .unwrap()
        .iter()
        .map(|v| {
            (
                v["host"].as_str().unwrap().to_string(),
                v["mount"].as_str().unwrap().to_string(),
            )
        })
        .collect();
    
    // Add volumes to sandbox config
    sandbox_config.volumes = volume_pairs;
}
```

## Complete Example: Extended PythonSandbox

Here's a complete example showing the extended implementation:

```python
# microsandbox/base_sandbox.py (extended)

from typing import List, Tuple, Optional
from pathlib import Path

class BaseSandbox(ABC):
    def __init__(
        self,
        server_url: str = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        # ... existing init code ...
        self._volumes: Optional[List[Tuple[str, str]]] = None

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        server_url: str = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        volumes: Optional[List[Tuple[str, str]]] = None,  # NEW
    ):
        """Create sandbox with optional volume mounts."""
        sandbox = cls(
            server_url=server_url,
            namespace=namespace,
            name=name,
            api_key=api_key,
        )
        try:
            sandbox._session = aiohttp.ClientSession()
            await sandbox.start(volumes=volumes)  # Pass volumes
            yield sandbox
        finally:
            await sandbox.stop()
            if sandbox._session:
                await sandbox._session.close()
                sandbox._session = None

    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
        volumes: Optional[List[Tuple[str, str]]] = None,  # NEW
    ) -> None:
        """Start sandbox with optional volume mounts."""
        if self._is_started:
            return

        sandbox_image = image or await self.get_default_image()
        
        config = {
            "image": sandbox_image,
            "memory": memory,
            "cpus": int(cpus),
        }
        
        # Add volumes to config
        if volumes:
            config["volumes"] = [
                {"host": str(Path(host).resolve()), "mount": mount}
                for host, mount in volumes
            ]
        
        request_data = {
            "jsonrpc": "2.0",
            "method": "sandbox.start",
            "params": {
                "namespace": self._namespace,
                "sandbox": self._name,
                "config": config,
            },
            "id": str(uuid.uuid4()),
        }
        
        # ... rest of start() implementation (HTTP request, etc.)
```

## Usage in Our Code

Once extended, we can use it like this:

```python
# client/sandbox_executor.py

from pathlib import Path

workspace_path = Path("./workspace").resolve()

async with PythonSandbox.create(
    name="code-execution",
    volumes=[(str(workspace_path), "/workspace")]  # Mount workspace
) as sandbox:
    # Files written to /workspace in sandbox are now persisted to host
    exec_result = await sandbox.run(code)
    output = await exec_result.output()
```

## Implementation Steps

1. **Fork microsandbox repository**
2. **Extend Python API** (`base_sandbox.py`):
   - Add `volumes` parameter to `create()` and `start()`
   - Format volumes in config JSON
3. **Extend Rust core** (if needed):
   - Ensure JSON-RPC handler accepts `volumes` in config
   - Pass to `patch_with_virtiofs_mounts` (already exists)
4. **Test**:
   - Create sandbox with volume mount
   - Write file to mounted directory
   - Verify file appears on host
5. **Submit PR** to microsandbox repository

## Alternative: Workaround (Current Implementation)

Until the extension is merged, we use the current workaround:
- Copy workspace files INTO sandbox at start
- Files persist within session
- Manual extraction needed for cross-session persistence

This provides partial persistence but requires extending microsandbox for full compliance with the Anthropic article.

