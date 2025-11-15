# Complete Implementation Guide: Volume Mounting Support

This guide provides **exact, step-by-step instructions** for implementing volume mounting support across all components.

---

## Overview

You need to change **3 components**:
1. **Python SDK** (`microsandbox/base_sandbox.py`) - Send volumes in JSON-RPC request
2. **Rust Server Payload** (`microsandbox-server/lib/payload.rs`) - Accept volumes in new format
3. **Rust Server Handler** (`microsandbox-server/lib/handler.rs`) - Process volumes

**Everything else is already implemented!** The volume mounting infrastructure in `sandbox.rs` (line 281) is complete.

---

## Component 1: Python SDK

### File: `microsandbox/base_sandbox.py`

#### Change 1.1: Add imports (Line 10)

**Find:**
```python
from typing import Optional
```

**Change to:**
```python
from typing import Optional, List, Tuple
```

#### Change 1.2: Add volumes parameter to `create()` (Line 77)

**Find:**
```python
    async def create(
        cls,
        server_url: str = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
```

**Change to:**
```python
    async def create(
        cls,
        server_url: str = None,
        namespace: str = "default",
        name: Optional[str] = None,
        api_key: Optional[str] = None,
        volumes: Optional[List[Tuple[str, str]]] = None,
    ):
```

#### Change 1.3: Update `create()` docstring (After line 86)

**Find:**
```python
            api_key: API key for Microsandbox server authentication. If not provided, it will be read from MSB_API_KEY environment variable.

        Returns:
```

**Add after the api_key line:**
```python
            volumes: List of (host_path, mount_path) tuples for volume mounts. Example: [("/host/workspace", "/workspace")]

        Returns:
```

#### Change 1.4: Pass volumes to `start()` (Line 109)

**Find:**
```python
            await sandbox.start()
```

**Change to:**
```python
            await sandbox.start(volumes=volumes)
```

#### Change 1.5: Add volumes parameter to `start()` (Line 124)

**Find:**
```python
    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
    ) -> None:
```

**Change to:**
```python
    async def start(
        self,
        image: Optional[str] = None,
        memory: int = 512,
        cpus: float = 1.0,
        timeout: float = 180.0,
        volumes: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
```

#### Change 1.6: Update `start()` docstring (After line 133)

**Find:**
```python
            timeout: Maximum time in seconds to wait for the sandbox to start (default: 180 seconds)

        Raises:
```

**Add after the timeout line:**
```python
            volumes: List of (host_path, mount_path) tuples for volume mounts. Example: [("/host/workspace", "/workspace")]

        Raises:
```

#### Change 1.7: Add volumes to config (After line 152)

**Find:**
```python
                "config": {
                    "image": sandbox_image,
                    "memory": memory,
                    "cpus": int(round(cpus)),
                },
            },
            "id": str(uuid.uuid4()),
        }
```

**Add right after the closing brace of `"id": ...` and before `headers = ...`:**
```python
                "id": str(uuid.uuid4()),
        }
        
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

---

## Component 2: Rust Server - Payload Definition

### File: `microsandbox-server/lib/payload.rs`

#### Change 2.1: Add VolumeMount struct

**Find the `SandboxConfig` struct definition (likely around where other structs are defined).**

**Add this struct BEFORE `SandboxConfig`:**
```rust
/// Volume mount configuration
#[derive(Debug, Deserialize, Clone)]
pub struct VolumeMount {
    /// Host path to mount
    pub host: String,
    /// Mount path inside sandbox
    pub mount: String,
}
```

#### Change 2.2: Update SandboxConfig struct

**Find:**
```rust
pub struct SandboxConfig {
    /// The image to use (optional for updates)
    pub image: Option<String>,

    /// The amount of memory in MiB to use
    pub memory: Option<u32>,

    /// The number of vCPUs to use
    pub cpus: Option<u8>,

    /// The volumes to mount
    #[serde(default)]
    pub volumes: Vec<String>,
```

**Change to:**
```rust
pub struct SandboxConfig {
    /// The image to use (optional for updates)
    pub image: Option<String>,

    /// The amount of memory in MiB to use
    pub memory: Option<u32>,

    /// The number of vCPUs to use
    pub cpus: Option<u8>,

    /// The volumes to mount
    #[serde(default)]
    pub volumes: Vec<VolumeMount>,
```

---

## Component 3: Rust Server - Handler

### File: `microsandbox-server/lib/handler.rs`

#### Change 3.1: Update volumes processing (Around line 500)

**Find:**
```rust
            if !config.volumes.is_empty() {
                let volumes_array = config
                    .volumes
                    .iter()
                    .map(|v| serde_yaml::Value::String(v.clone()))
                    .collect::<Vec<_>>();
                sandbox_map.insert(
                    serde_yaml::Value::String("volumes".to_string()),
                    serde_yaml::Value::Sequence(volumes_array),
                );
            }
```

**Replace with:**
```rust
            if !config.volumes.is_empty() {
                // Convert VolumeMount to "host:mount" string format for YAML config
                // The YAML config loader expects volumes as strings in "host:mount" format,
                // which it then parses into PathPair types
                let volumes_array: Vec<serde_yaml::Value> = config
                    .volumes
                    .iter()
                    .map(|v| {
                        serde_yaml::Value::String(format!("{}:{}", v.host, v.mount))
                    })
                    .collect();
                
                sandbox_map.insert(
                    serde_yaml::Value::String("volumes".to_string()),
                    serde_yaml::Value::Sequence(volumes_array),
                );
            }
```

**Note:** The YAML config expects volumes as strings in `"host:mount"` format (e.g., `"/workspace:/workspace"`), which the config loader then parses into `PathPair` types. The handler converts `VolumeMount` structs to this string format.

---

## Verification Checklist

After making all changes:

- [ ] Python SDK: `base_sandbox.py` - 7 changes made
- [ ] Rust Server: `payload.rs` - 2 changes made (VolumeMount struct + SandboxConfig update)
- [ ] Rust Server: `handler.rs` - 1 change made (volumes processing)

---

## Testing

### 1. Rebuild Components

```bash
cd /path/to/microsandbox

# Rebuild Rust server
cargo build --release
cargo install --path . --force

# Reinstall Python SDK
pip install -e .
```

### 2. Restart Server

```bash
msb server stop
msb server start --dev
```

### 3. Test Volume Mounting

```python
import asyncio
from pathlib import Path
from microsandbox import PythonSandbox

async def test():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    async with PythonSandbox.create(
        name="test-volumes",
        volumes=[(str(workspace), "/workspace")]
    ) as sandbox:
        result = await sandbox.run('''
with open("/workspace/test.txt", "w") as f:
    f.write("Hello from sandbox!")
print("File written to /workspace/test.txt")
''')
        print(await result.output())
    
    # Verify file exists on host
    test_file = workspace / "test.txt"
    if test_file.exists():
        print(f"✅ SUCCESS! File found at {test_file}")
        print(f"   Content: {test_file.read_text()}")
    else:
        print("❌ FAILED - File not found on host")

asyncio.run(test())
```

---

## Summary

**Total Changes:**
- **Python SDK:** 7 changes in 1 file (`base_sandbox.py`)
- **Rust Server:** 3 changes in 2 files (`payload.rs` + `handler.rs`)

**What's Already Done:**
- ✅ Volume mounting infrastructure in `sandbox.rs` (line 281)
- ✅ `patch_with_virtiofs_mounts()` function
- ✅ Config struct support for volumes
- ✅ Command-line argument handling for `--mapped-dir`

**What You're Adding:**
- Python SDK sends volumes in JSON-RPC request
- Rust server accepts volumes in `{"host": "...", "mount": "..."}` format
- Rust server converts to YAML config format

That's it! These are ALL the changes needed.

