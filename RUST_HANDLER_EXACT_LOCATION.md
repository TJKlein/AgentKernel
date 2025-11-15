# Exact Location for Rust Handler Changes

## File Location

**File:** `microsandbox-server/lib/handler.rs`

**Function:** `sandbox_start_impl` (starts at line 345)

**Current volumes handling:** Lines 500-510 (volumes are already handled, but format needs updating)

## Current Code (Lines 500-510)

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

**Issue:** `config.volumes` is currently `Vec<String>` (expects format like `["host:mount"]`), but Python SDK sends `[{"host": "...", "mount": "..."}]`.

## Changes Needed

### Change 1: Update `SandboxConfig` struct

**File:** `microsandbox-server/lib/payload.rs`

**Current:**
```rust
pub struct SandboxConfig {
    // ...
    /// The volumes to mount
    #[serde(default)]
    pub volumes: Vec<String>,  // CHANGE THIS
}
```

**Change to:**
```rust
#[derive(Debug, Deserialize)]
pub struct VolumeMount {
    pub host: String,
    pub mount: String,
}

pub struct SandboxConfig {
    // ...
    /// The volumes to mount
    #[serde(default)]
    pub volumes: Vec<VolumeMount>,  // CHANGE TO THIS
}
```

### Change 2: Update volumes parsing in handler

**File:** `microsandbox-server/lib/handler.rs` (around line 500)

**Replace the existing volumes code with:**

```rust
if !config.volumes.is_empty() {
    // Convert VolumeMount to PathPair format for YAML config
    use microsandbox_core::config::PathPair;
    use typed_path::Utf8UnixPathBuf;
    
    let volumes_array: Vec<serde_yaml::Value> = config
        .volumes
        .iter()
        .map(|v| {
            // Create PathPair from VolumeMount
            let path_pair = PathPair::Distinct {
                host: Utf8UnixPathBuf::from(v.host.clone()),
                guest: Utf8UnixPathBuf::from(v.mount.clone()),
            };
            
            // Convert to YAML format (host:mount string)
            serde_yaml::Value::String(format!("{}:{}", v.host, v.mount))
        })
        .collect();
    
    sandbox_map.insert(
        serde_yaml::Value::String("volumes".to_string()),
        serde_yaml::Value::Sequence(volumes_array),
    );
}
```

**Note:** The YAML config expects volumes as strings in `"host:mount"` format, which is then parsed by the config loader into `PathPair` types. So we just need to convert the `VolumeMount` structs to that string format.

## Summary

- **File:** `microsandbox-server/lib/handler.rs`
- **Function:** `sandbox_start_impl`
- **Location:** After line 500 (after parsing `cpus`)
- **What to add:** Parse `config.volumes` and add to `yaml_config`

