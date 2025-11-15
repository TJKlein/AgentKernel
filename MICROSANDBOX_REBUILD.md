# What Needs to be Rebuilt After Microsandbox Extension

## Short Answer

**No, you don't need to rebuild the container images** (like `microsandbox/python`).

You DO need to:
1. **Rebuild the Rust server binary** (`msb`) - if you modify Rust code
2. **Reinstall the Python package** - if you modify Python SDK code

## Architecture Breakdown

Microsandbox has three components:

### 1. Python SDK (`microsandbox` package)
- **Location**: Installed via pip (e.g., `.venv/lib/python3.11/site-packages/microsandbox`)
- **Changes**: Modify `base_sandbox.py`
- **Rebuild needed**: Just reinstall the package
  ```bash
  pip install -e /path/to/microsandbox  # If developing locally
  # OR
  pip install microsandbox  # If installing from your fork
  ```

### 2. Rust Server (`msb` binary)
- **Location**: `/Users/d065243/.local/bin/msb` (or similar)
- **Changes**: Modify Rust handler code
- **Rebuild needed**: Rebuild the Rust binary
  ```bash
  cd /path/to/microsandbox
  cargo build --release
  # Then copy or install the binary
  ```

### 3. Container Images (`microsandbox/python`, etc.)
- **Location**: Docker images pulled from registry
- **Changes**: None needed for volume support
- **Rebuild needed**: ❌ **NO** - These are just execution environments

## Why Container Images Don't Need Rebuilding

The container images (`microsandbox/python`) are just execution environments - they contain:
- Python runtime
- Basic system libraries
- Standard Python packages

Volume mounting happens **at the sandbox creation level** (handled by the Rust server), not inside the container image. The `patch_with_virtiofs_mounts` function in the Rust core handles mounting host directories into the running container - this is a runtime operation, not a build-time operation.

## Development Workflow

If you're extending microsandbox:

1. **Fork the repository**
2. **Make Python SDK changes** → Reinstall Python package
3. **Make Rust server changes** → Rebuild `msb` binary
4. **Test** → Use existing container images (no rebuild needed)
5. **Submit PR**

## Testing Without Rebuilding Containers

You can test volume mounting immediately after:
- Reinstalling the Python SDK
- Rebuilding the `msb` server binary

The existing `microsandbox/python` container image will work fine - it doesn't need to know about volumes. The volume mounting is handled by the server when creating the sandbox.

## Summary

| Component | Needs Rebuild? | How |
|-----------|---------------|-----|
| Python SDK | ✅ Yes | `pip install -e .` |
| Rust Server (`msb`) | ✅ Yes | `cargo build --release` |
| Container Images | ❌ No | Use existing images |

The container images are just execution environments - volume mounting is a server-side feature, not a container feature.

