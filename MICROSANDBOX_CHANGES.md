# Exact Lines to Change in Microsandbox Repository

## File: `microsandbox/base_sandbox.py`

### Change 1: Add import (line 10)
**Line 10:** Add `List, Tuple` to imports
```python
from typing import Optional, List, Tuple  # Add List, Tuple
```

### Change 2: Add volumes to __init__ (line 58)
**After line 57:** Add volumes instance variable
```python
        self._api_key = api_key or os.environ.get("MSB_API_KEY")
        self._volumes: Optional[List[Tuple[str, str]]] = None  # ADD THIS LINE
        self._session = None
```

### Change 3: Add volumes parameter to create() (line 77)
**Line 77:** Add `volumes` parameter
```python
        api_key: Optional[str] = None,
        volumes: Optional[List[Tuple[str, str]]] = None,  # ADD THIS LINE
    ):
```

### Change 4: Update create() docstring (line 86)
**After line 86:** Add volumes to docstring
```python
            api_key: API key for Microsandbox server authentication. If not provided, it will be read from MSB_API_KEY environment variable.
            volumes: List of (host_path, mount_path) tuples for volume mounts. Example: [("/host/workspace", "/workspace")]  # ADD THIS LINE
```

### Change 5: Pass volumes to start() (line 109)
**Line 109:** Change to pass volumes
```python
            await sandbox.start(volumes=volumes)  # Change from: await sandbox.start()
```

### Change 6: Add volumes parameter to start() (line 124)
**Line 124:** Add `volumes` parameter
```python
        timeout: float = 180.0,
        volumes: Optional[List[Tuple[str, str]]] = None,  # ADD THIS LINE
    ) -> None:
```

### Change 7: Update start() docstring (line 133)
**After line 133:** Add volumes to docstring
```python
            timeout: Maximum time in seconds to wait for the sandbox to start (default: 180 seconds)
            volumes: List of (host_path, mount_path) tuples for volume mounts. Example: [("/host/workspace", "/workspace")]  # ADD THIS LINE
```

### Change 8: Add volumes to config (after line 152)
**After line 152:** Add volumes to request_data config
```python
                    "cpus": int(round(cpus)),
                },
            },
            "id": str(uuid.uuid4()),
        }
        
        # ADD THIS BLOCK:
        # Add volumes to config if provided
        if volumes:
            from pathlib import Path
            request_data["params"]["config"]["volumes"] = [
                {
                    "host": str(Path(host_path).resolve()),
                    "mount": mount_path
                }
                for host_path, mount_path in volumes
            ]
        
        headers = {"Content-Type": "application/json"}
```

## File: `microsandbox-core/src/handlers/sandbox.rs` (or equivalent)

**Location:** In the `sandbox.start` JSON-RPC handler, after parsing `memory` and `cpus` from config:

```rust
// Find where config is parsed (likely after parsing memory/cpus)
// ADD THIS BLOCK:

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
        
        // Set volumes in sandbox config
        // This will be used by patch_with_virtiofs_mounts in sandbox.rs
        sandbox_config.volumes = volume_pairs;
    }
}
```

## Summary

**Python changes:** 8 locations in `base_sandbox.py`
**Rust changes:** 1 location in the JSON-RPC handler (exact file location depends on microsandbox structure)

The Rust core already has `patch_with_virtiofs_mounts` - you just need to pass the volumes data to it.

