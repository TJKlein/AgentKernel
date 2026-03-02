"""
Visual diff showing exact code changes needed to extend microsandbox.

This shows the before/after for each file that needs modification.
"""

# ============================================================================
# FILE: microsandbox/base_sandbox.py
# ============================================================================

BASE_SANDBOX_DIFF = """
--- a/microsandbox/base_sandbox.py
+++ b/microsandbox/base_sandbox.py
@@ -1,6 +1,7 @@
 from typing import Optional
+from typing import List, Tuple
 from pathlib import Path
 
@@ -20,6 +21,7 @@ class BaseSandbox(ABC):
         self._namespace = namespace
         self._name = name or f"sandbox-{uuid.uuid4().hex[:8]}"
         self._api_key = api_key or os.environ.get("MSB_API_KEY")
+        self._volumes: Optional[List[Tuple[str, str]]] = None
         self._session = None
         self._is_started = False
 
@@ -30,6 +32,7 @@ class BaseSandbox(ABC):
     @classmethod
     @asynccontextmanager
     async def create(
         cls,
         server_url: str = None,
         namespace: str = "default",
         name: Optional[str] = None,
         api_key: Optional[str] = None,
+        volumes: Optional[List[Tuple[str, str]]] = None,
     ):
         \"\"\"
         Create and initialize a new sandbox as an async context manager.
@@ -37,6 +40,8 @@ class BaseSandbox(ABC):
         Args:
             server_url: URL of the Microsandbox server
             namespace: Namespace for the sandbox
             name: Optional name for the sandbox
             api_key: API key for authentication
+            volumes: List of (host_path, mount_path) tuples for volume mounts
+                     Example: [("/host/workspace", "/workspace")]
         \"\"\"
         sandbox = cls(
             server_url=server_url,
@@ -47,7 +52,7 @@ class BaseSandbox(ABC):
         try:
             sandbox._session = aiohttp.ClientSession()
-            await sandbox.start()
+            await sandbox.start(volumes=volumes)
             yield sandbox
         finally:
             await sandbox.stop()
@@ -58,6 +63,7 @@ class BaseSandbox(ABC):
     async def start(
         self,
         image: Optional[str] = None,
         memory: int = 512,
         cpus: float = 1.0,
         timeout: float = 180.0,
+        volumes: Optional[List[Tuple[str, str]]] = None,
     ) -> None:
         \"\"\"
         Start the sandbox container.
@@ -66,6 +72,8 @@ class BaseSandbox(ABC):
             memory: Memory limit in MB
             cpus: CPU limit
             timeout: Maximum time in seconds to wait for the sandbox to start
+            volumes: List of (host_path, mount_path) tuples for volume mounts
+                     Example: [("/host/workspace", "/workspace")]
         \"\"\"
         if self._is_started:
             return
@@ -73,11 +81,20 @@ class BaseSandbox(ABC):
         sandbox_image = image or await self.get_default_image()
         request_data = {
             "jsonrpc": "2.0",
             "method": "sandbox.start",
             "params": {
                 "namespace": self._namespace,
                 "sandbox": self._name,
                 "config": {
                     "image": sandbox_image,
                     "memory": memory,
                     "cpus": int(cpus),
                 },
             },
             "id": str(uuid.uuid4()),
         }
+        
+        # Add volumes to config if provided
+        if volumes:
+            request_data["params"]["config"]["volumes"] = [
+                {
+                    "host": str(Path(host_path).resolve()),
+                    "mount": mount_path
+                }
+                for host_path, mount_path in volumes
+            ]
         
         # ... rest of existing start() implementation ...
"""

# ============================================================================
# FILE: microsandbox-core/src/handlers/sandbox.rs (example location)
# ============================================================================

RUST_HANDLER_DIFF = """
--- a/microsandbox-core/src/handlers/sandbox.rs
+++ b/microsandbox-core/src/handlers/sandbox.rs
@@ -100,6 +100,25 @@ pub async fn handle_sandbox_start(
         sandbox_config.memory = config.get("memory").and_then(|v| v.as_u64()).map(|v| v as u32);
         sandbox_config.cpus = config.get("cpus").and_then(|v| v.as_f64()).map(|v| v as f32);
         
+        // Parse volumes from config
+        if let Some(volumes_value) = config.get("volumes") {
+            if let Some(volumes_array) = volumes_value.as_array() {
+                let mut volume_pairs = Vec::new();
+                
+                for vol in volumes_array {
+                    if let (Some(host), Some(mount)) = (
+                        vol.get("host").and_then(|v| v.as_str()),
+                        vol.get("mount").and_then(|v| v.as_str()),
+                    ) {
+                        volume_pairs.push((
+                            host.to_string(),
+                            mount.to_string(),
+                        ));
+                    }
+                }
+                
+                // Set volumes in sandbox config
+                // This will be used by patch_with_virtiofs_mounts in sandbox.rs
+                sandbox_config.volumes = volume_pairs;
+            }
+        }
+        
         // ... rest of handler ...
     }
"""

# ============================================================================
# USAGE IN OUR CODEBASE
# ============================================================================

OUR_CODE_USAGE = """
# client/sandbox_executor.py - After extension

--- a/client/sandbox_executor.py
+++ b/client/sandbox_executor.py
@@ -104,7 +104,12 @@ class SandboxExecutor(CodeExecutor):
             # Note: microsandbox Rust core supports volumes via patch_with_virtiofs_mounts,
             # but Python API doesn't expose this yet. For now, we copy workspace files in.
-            # TODO: Extend PythonSandbox.create() to support volumes parameter
-            async with PythonSandbox.create(name="code-execution") as sandbox:
+            # 
+            # After microsandbox extension, we can use:
+            workspace_path_abs = workspace_path.resolve()
+            async with PythonSandbox.create(
+                name="code-execution",
+                volumes=[(str(workspace_path_abs), "/workspace")]
+            ) as sandbox:
                 import asyncio
 
                 try:
-                    # Copy workspace files into sandbox (for state persistence)
-                    # This allows code to read previous state
-                    workspace_files_code = self._generate_workspace_copy_in_code(workspace_path)
-                    if workspace_files_code:
-                        workspace_setup_result = await asyncio.wait_for(
-                            sandbox.run(workspace_files_code), timeout=10.0
-                        )
-                        workspace_setup_output = await workspace_setup_result.output()
-                        if workspace_setup_output and "Setup error:" in workspace_setup_output:
-                            return workspace_setup_output, workspace_setup_output
+                    # Workspace is now mounted, no need to copy files!
+                    # Files written to /workspace in sandbox are automatically
+                    # persisted to host workspace directory
"""

if __name__ == "__main__":
    print("=" * 70)
    print("MICROSANDBOX EXTENSION - VISUAL DIFF")
    print("=" * 70)
    print("\n1. Python API Changes (base_sandbox.py):")
    print("-" * 70)
    print(BASE_SANDBOX_DIFF)
    print("\n2. Rust Core Changes (handler.rs):")
    print("-" * 70)
    print(RUST_HANDLER_DIFF)
    print("\n3. Usage in Our Codebase:")
    print("-" * 70)
    print(OUR_CODE_USAGE)

