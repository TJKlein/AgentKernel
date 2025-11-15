# Workspace Persistence Implementation

## Current Status

The workspace directory (`./workspace`) is used for state persistence, but there's a limitation:

### What Works ✅
- **Reading previous state**: Workspace files are copied INTO the sandbox at execution start
- **Within-session persistence**: Files written to `workspace/` in sandbox persist between sequential `sandbox.run()` calls

### What Doesn't Work ❌
- **Cross-session persistence**: Files written to `workspace/` in sandbox don't automatically sync back to host `./workspace` directory
- **Reason**: microsandbox Python API doesn't support directory mounting

## How It Should Work (Anthropic Article)

According to the [Anthropic article](https://www.anthropic.com/engineering/code-execution-with-mcp), the workspace should be:
- Mounted or accessible from the sandbox
- Files written to workspace persist across different executions
- Agents can resume work by reading from workspace

## microsandbox Support

The microsandbox **Rust core** supports volume mounts via `patch_with_virtiofs_mounts`:
- See: https://github.com/zerocore-ai/microsandbox/blob/0d99770d6d0da1046dec8d1e0fc7da3bf4dee407/microsandbox-core/lib/management/sandbox.rs#L636
- Volumes are configured in the sandbox config and mounted using virtiofs

However, the **Python API** (`PythonSandbox.create()`) doesn't expose this functionality:
```python
PythonSandbox.create(
    server_url: str = None,
    namespace: str = 'default',
    name: Optional[str] = None,
    api_key: Optional[str] = None
)
# No volumes parameter!
```

## Solutions

### Option 1: Extend microsandbox Python API (Recommended)
Add volume support to `PythonSandbox.create()`:

```python
PythonSandbox.create(
    name="code-execution",
    volumes=[("/workspace", str(workspace_path.resolve()))]  # New parameter
)
```

This would require modifying the microsandbox Python package to pass volumes to the Rust core.

### Option 2: Use microsandbox Config File
Create a `microsandbox.toml` config file with volumes defined, but this requires:
- Config file management
- Ensuring Python API respects the config
- More complex setup

### Option 3: Workaround (Current Implementation)
- Copy workspace files INTO sandbox at start (✅ implemented)
- Files written to workspace/ persist within session (✅ works)
- Manual extraction needed for cross-session persistence (⚠️ limitation)

## Current Implementation

The current code:
1. Copies workspace files into sandbox at execution start
2. Code can read previous state from `workspace/` directory
3. Code can write to `workspace/` directory (persists within session)
4. Files don't automatically sync back to host (limitation)

This provides **partial persistence** - agents can read previous state but can't write persistent state back to host without extending microsandbox.

