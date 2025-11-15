# Exact Rust Server Changes for Volume Support

## File Location

The changes need to be made in the **JSON-RPC handler** that processes `sandbox.start` requests.

**Likely file:** `microsandbox-core/src/handlers/sandbox.rs` or similar handler file

## What to Find

Look for code that handles the `sandbox.start` JSON-RPC method. You should see something like:

```rust
pub async fn handle_sandbox_start(
    // ... parameters ...
    config: &Value,  // JSON config from request
    // ...
) -> Result<...> {
    // ... existing code ...
    
    // Parse memory and cpus from config
    sandbox_config.memory = config.get("memory").and_then(|v| v.as_u64()).map(|v| v as u32);
    sandbox_config.cpus = config.get("cpus").and_then(|v| v.as_f64()).map(|v| v as f32);
    
    // ... rest of handler ...
}
```

## Exact Code to Add

**Location:** Right after parsing `memory` and `cpus`, before the rest of the handler code.

**Add this block:**

```rust
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

## Complete Example (Before/After)

### Before:
```rust
pub async fn handle_sandbox_start(
    // ... parameters ...
    config: &Value,
    // ...
) -> Result<...> {
    // ... existing code ...
    
    // Parse memory and cpus
    sandbox_config.memory = config.get("memory").and_then(|v| v.as_u64()).map(|v| v as u32);
    sandbox_config.cpus = config.get("cpus").and_then(|v| v.as_f64()).map(|v| v as f32);
    
    // ... rest of handler (calls setup functions, etc.) ...
}
```

### After:
```rust
pub async fn handle_sandbox_start(
    // ... parameters ...
    config: &Value,
    // ...
) -> Result<...> {
    // ... existing code ...
    
    // Parse memory and cpus
    sandbox_config.memory = config.get("memory").and_then(|v| v.as_u64()).map(|v| v as u32);
    sandbox_config.cpus = config.get("cpus").and_then(|v| v.as_f64()).map(|v| v as f32);
    
    // ADD THIS BLOCK: Parse volumes from config
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
    
    // ... rest of handler (calls setup functions, etc.) ...
}
```

## Important Notes

1. **`sandbox_config.volumes` field must exist**: The `Sandbox` config struct needs a `volumes` field of type `Vec<(String, String)>` or similar. If it doesn't exist, you'll need to add it to the struct definition.

2. **The mounting logic already exists**: The `patch_with_virtiofs_mounts` function in `sandbox.rs` (line 636) already handles the actual mounting. You just need to ensure `sandbox_config.volumes` is populated.

3. **JSON format expected**: The Python SDK sends volumes as:
   ```json
   {
     "volumes": [
       {"host": "/absolute/host/path", "mount": "/sandbox/path"},
       ...
     ]
   }
   ```

## How to Find the Handler

1. Search for `"sandbox.start"` in the Rust codebase
2. Look for JSON-RPC method handlers
3. Find where `config.get("memory")` and `config.get("cpus")` are parsed
4. Add the volumes parsing code right after those lines

## Verification

After making the change, the handler should:
1. Receive `volumes` in the JSON config from Python SDK
2. Parse it into `Vec<(String, String)>`
3. Set `sandbox_config.volumes`
4. The existing `patch_with_virtiofs_mounts` function will use it automatically

That's it! The Rust core already has the mounting infrastructure - you just need to pass the data through.

