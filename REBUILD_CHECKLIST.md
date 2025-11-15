# Rebuild Checklist for Microsandbox Extension

## What Needs Rebuilding Based on Your Changes

### Scenario 1: Only Python SDK Changes
**If you only modify:** `microsandbox/base_sandbox.py`

**Rebuild needed:**
- ✅ Reinstall Python package
- ❌ No server binary rebuild needed
- ❌ No container rebuild needed

**Commands:**
```bash
cd /path/to/microsandbox
pip install -e .  # Reinstall Python SDK
```

**Note:** This won't work fully because the Rust server won't understand the `volumes` parameter in the JSON-RPC request. You'll get an error when trying to use volumes.

---

### Scenario 2: Only Rust Server Changes
**If you only modify:** Rust handler code

**Rebuild needed:**
- ✅ Rebuild `msb` server binary
- ❌ No Python package reinstall needed (but volumes won't be accessible from Python)
- ❌ No container rebuild needed

**Commands:**
```bash
cd /path/to/microsandbox
cargo build --release
# Install the binary (method depends on microsandbox build system)
# Usually: cp target/release/msb ~/.local/bin/msb
# Or: cargo install --path .
```

**Note:** This won't work fully because the Python SDK won't send the `volumes` parameter. You need both changes.

---

### Scenario 3: Full Extension (Recommended)
**If you modify:** Both Python SDK AND Rust server

**Rebuild needed:**
- ✅ Reinstall Python package
- ✅ Rebuild `msb` server binary
- ❌ No container rebuild needed

**Commands:**
```bash
cd /path/to/microsandbox

# 1. Rebuild Rust server binary
cargo build --release
# Install binary (check microsandbox docs for exact command)
# Usually: cargo install --path . --force

# 2. Reinstall Python SDK
pip install -e .  # If developing locally
# OR
pip install .  # If installing from source

# 3. Restart the server
msb server stop  # If running
msb server start --dev
```

---

## Quick Test After Rebuild

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
    f.write("Hello!")
print("File written")
''')
        print(await result.output())
    
    # Check if file exists on host
    if (workspace / "test.txt").exists():
        print("✅ Volume mounting works!")
    else:
        print("❌ Volume mounting failed")

asyncio.run(test())
```

---

## Summary

| Changes Made | Python SDK | Server Binary | Containers |
|-------------|------------|---------------|------------|
| Python only | ✅ Reinstall | ❌ No | ❌ No |
| Rust only | ❌ No | ✅ Rebuild | ❌ No |
| **Both (full)** | ✅ Reinstall | ✅ Rebuild | ❌ No |

**For the extension to work, you need BOTH Python and Rust changes, so you need to rebuild both.**

