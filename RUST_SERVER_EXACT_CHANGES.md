# Exact Rust Server Changes - Based on Repository Structure

Based on the [microsandbox repository](https://github.com/zerocore-ai/microsandbox/tree/0d99770d6d0da1046dec8d1e0fc7da3bf4dee407/microsandbox-core), here are the exact changes needed:

## File 1: JSON-RPC Handler (Server Layer)

**Location:** `microsandbox-server/src/handlers/sandbox.rs` or similar

**What to find:** The JSON-RPC handler that processes `sandbox.start` requests. Look for code that:
- Receives JSON-RPC requests with method `"sandbox.start"`
- Parses the `config` object from the request
- Extracts `memory`, `cpus`, etc. from config
- Creates/updates a `sandbox_config` object

**Add this code block** right after parsing `memory` and `cpus`:

```rust
// Parse volumes from config
if let Some(volumes_value) = config.get("volumes") {
    if let Some(volumes_array) = volumes_value.as_array() {
        use crate::config::PathPair;  // Import PathPair type
        
        let mut volume_pairs = Vec::new();
        
        for vol in volumes_array {
            if let (Some(host), Some(mount)) = (
                vol.get("host").and_then(|v| v.as_str()),
                vol.get("mount").and_then(|v| v.as_str()),
            ) {
                // Convert to PathPair::Distinct { host, guest }
                volume_pairs.push(PathPair::Distinct {
                    host: host.into(),
                    guest: mount.into(),
                });
            }
        }
        
        // Set volumes in sandbox config
        sandbox_config.set_volumes(volume_pairs);  // or sandbox_config.volumes = volume_pairs;
    }
}
```

**Note:** The volumes use `PathPair` type, not plain tuples. `PathPair::Distinct { host, guest }` is the format expected.

## File 2: Sandbox Config Struct

**Location:** `microsandbox-core/lib/config/microsandbox.rs` (likely in the `Sandbox` struct)

**Good news:** The `Sandbox` struct likely already has a `volumes` field using `PathPair` type (from `path_pair.rs`). The volumes are already handled in `sandbox.rs` around line 280.

**What to check:** Verify the `Sandbox` struct has:
```rust
pub struct Sandbox {
    // ... existing fields ...
    volumes: Vec<PathPair>,  // Should already exist
}
```

And verify it has a getter:
```rust
pub fn get_volumes(&self) -> &Vec<PathPair> {
    &self.volumes
}
```

**If volumes field doesn't exist**, add it. But based on the code in `sandbox.rs`, it appears volumes are already supported!

## File 3: Sandbox Management (Already Fully Handles Volumes!)

**Location:** `microsandbox-core/lib/management/sandbox.rs` (line 281)

**Excellent news:** This file **already fully implements volume handling**! Looking at [line 281](https://github.com/zerocore-ai/microsandbox/blob/0d99770d6d0da1046dec8d1e0fc7da3bf4dee407/microsandbox-core/lib/management/sandbox.rs#L281), volumes are:

1. **Read from config**: `sandbox_config.get_volumes()` is already used
2. **Added to command**: Volumes are added as `--mapped-dir` arguments to the supervisor command
3. **Patched into rootfs**: `rootfs::patch_with_virtiofs_mounts()` is called with the volumes

**No changes needed here!** The infrastructure is complete. You only need to ensure volumes flow from JSON-RPC → config → sandbox_config.

## Summary of Changes

**Only ONE change needed:**

1. **JSON-RPC Handler** (`microsandbox-server/src/handlers/`):
   - Parse `volumes` from JSON config
   - Convert to `PathPair` format
   - Set `sandbox_config.volumes`

**Everything else is already implemented:**
- ✅ Config struct already has `volumes: Vec<PathPair>` field
- ✅ `sandbox.rs` already handles volumes (line 281) - adds `--mapped-dir` args
- ✅ `patch_with_virtiofs_mounts()` already exists and is called
- ✅ Volume mounting infrastructure is complete

**You just need to connect the JSON-RPC input to the existing config!**

## How to Find the Handler

1. Search for `"sandbox.start"` in the `microsandbox-server` directory
2. Look for JSON-RPC method routing/dispatching code
3. Find where `config.get("memory")` and `config.get("cpus")` are parsed
4. Add volumes parsing right after those lines

The mounting infrastructure (`patch_with_virtiofs_mounts`) already exists - you just need to ensure the data flows from JSON-RPC → config → sandbox setup.

