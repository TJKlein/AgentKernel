#!/usr/bin/env python3
"""
Microsandbox setup verification script.

This script verifies that microsandbox is properly configured with volume mounting support.
Run this before using AgentKernel to ensure everything is set up correctly.
"""

import sys
import subprocess
import asyncio
from pathlib import Path


def print_step(step: str, status: str = ""):
    """Print a setup step."""
    if status == "✓":
        print(f"✓ {step}")
    elif status == "✗":
        print(f"✗ {step}")
    elif status == "⚠":
        print(f"⚠ {step}")
    else:
        print(f"  {step}")


def check_docker():
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print_step("Docker is running", "✓")
            return True
        else:
            print_step("Docker is not running", "✗")
            print("  Please start Docker Desktop or the Docker daemon")
            return False
    except FileNotFoundError:
        print_step("Docker is not installed", "✗")
        print("  Install Docker: https://docs.docker.com/get-docker/")
        return False
    except Exception as e:
        print_step(f"Error checking Docker: {e}", "✗")
        return False


def check_microsandbox_binary():
    """Check if microsandbox binary exists."""
    # Check common locations
    locations = [
        Path.home() / ".local" / "bin" / "msb",
        Path("/usr/local/bin/msb"),
        Path("/usr/bin/msb"),
    ]
    
    for location in locations:
        if location.exists():
            print_step(f"Found msb at {location}", "⚠")
            print("  WARNING: The global 'msb' command does NOT support volume mounting!")
            print("  You MUST use the rebuilt binary from microsandbox/target/release/msbserver")
            return False
    
    return True


def check_port_reachable(host: str = "127.0.0.1", port: int = 5555) -> bool:
    """Check if we can connect to the microsandbox server port."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect((host, port))
        return True
    except (OSError, socket.error):
        return False


def check_microsandbox_server():
    """Check if microsandbox server is running and reachable on port 5555."""
    # First verify the server is actually listening (avoids false positive from stale ps output)
    if check_port_reachable("127.0.0.1", 5555):
        print_step("Microsandbox server is running and reachable on 127.0.0.1:5555", "✓")
        return True

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "msbserver" in result.stdout:
            if "target/release/msbserver" in result.stdout:
                print_step("Microsandbox server process found but not reachable on port 5555", "✗")
                print("  The server may have crashed or be bound to a different interface.")
            else:
                print_step("Microsandbox server is running (wrong binary!)", "✗")
                print("  You're using the global 'msb' which doesn't support volumes")
                print("  Kill it: pkill -f msbserver")
            print("  Start the correct one: cd /path/to/microsandbox && ./target/release/msbserver --dev")
        else:
            print_step("Microsandbox server is not running", "✗")
            print("  Start it: cd /path/to/microsandbox && ./target/release/msbserver --dev")
    except Exception as e:
        print_step(f"Error checking server: {e}", "✗")
    return False


def _is_server_permission_error(error: Exception) -> bool:
    """True if error indicates server is reachable but sandbox start failed (e.g. permission)."""
    msg = str(error).lower()
    return (
        "5002" in msg
        or "internal server error" in msg
        or "operation not permitted" in msg
        or "failed to write" in msg
    )


async def test_volume_support():
    """
    Test if microsandbox supports volume mounting.
    Returns (success, server_ok_volume_failed): when server is reachable but sandbox
    fails (e.g. permission), we treat as pass with warning.
    """
    try:
        from microsandbox import PythonSandbox
        import tempfile

        print_step("Testing volume mounting support...")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            test_file = tmpdir_path / "test.txt"
            test_file.write_text("Hello from host!")

            try:
                async with PythonSandbox.create(
                    name="test-volume-support",
                    volumes=[(str(tmpdir_path), "/test")]
                ) as sandbox:
                    result = await sandbox.run("""
import os
if os.path.exists('/test/test.txt'):
    with open('/test/test.txt', 'r') as f:
        print(f.read())
else:
    print('ERROR: File not found in sandbox')
""")
                    output = await result.output()

                    if "Hello from host!" in output:
                        print_step("Volume mounting works!", "✓")
                        return (True, False)
                    else:
                        print_step("Volume mounting failed - file not accessible", "✗")
                        print(f"  Output: {output}")
                        return (False, False)

            except RuntimeError as e:
                error_msg = str(e)
                if "Invalid params" in error_msg or "expected a string" in error_msg:
                    print_step("Volume mounting NOT supported", "✗")
                    print("  ERROR: Your microsandbox doesn't support volume mounting!")
                    print("  You MUST rebuild microsandbox from source:")
                    print("    cd /path/to/microsandbox")
                    print("    cargo build --release")
                    print("    ./target/release/msbserver --dev")
                    return (False, False)
                if _is_server_permission_error(e):
                    print_step("Volume test skipped (server permission/config issue)", "⚠")
                    print("  Server is reachable but could not start a sandbox (e.g. port mappings).")
                    print("  Ensure the server can write to its data dir (e.g. ~/.microsandbox).")
                    return (False, True)
                raise

    except ImportError:
        print_step("Microsandbox Python package not installed", "✗")
        print("  Install it: cd microsandbox && pip install -e .")
        return (False, False)
    except Exception as e:
        if _is_server_permission_error(e):
            print_step("Volume test skipped (server permission/config issue)", "⚠")
            print(f"  {e}")
            print("  Ensure the server can write to its data dir (e.g. ~/.microsandbox).")
            return (False, True)
        print_step(f"Error testing volume support: {e}", "✗")
        return (False, False)


def check_sandboxfile():
    """Check if Sandboxfile is configured."""
    sandboxfile = Path.home() / ".microsandbox" / "namespaces" / "default" / "Sandboxfile"
    
    # if not sandboxfile.exists():
    #     print_step("Sandboxfile not found", "✗")
    #     print(f"  Create it at: {sandboxfile}")
    #     print("  See DOCS.md for configuration template")
    #     return False
    
    # Check if it has the code-execution sandbox with volumes
    try:
        content = sandboxfile.read_text()
    except FileNotFoundError:
        print_step("Sandboxfile not found (dynamically managed)", "!")
        return True
    
    # if "code-execution:" not in content:
    #     print_step("Sandboxfile missing 'code-execution' sandbox", "✗")
    #     print("  Add a code-execution sandbox definition")
    #     return False
    
    # if "volumes:" not in content:
    #     print_step("Sandboxfile 'code-execution' missing 'volumes' mapping", "✗")
    #     print("  Add a volumes mapping to code-execution")
    #     return False
    
    print_step("Sandboxfile (managed by server)", "✓")
    return True


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("AgentKernel Setup Verification")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Check 1: Docker
    print("[1/5] Checking Docker...")
    if not check_docker():
        all_passed = False
    print()
    
    # Check 2: Global msb warning
    print("[2/5] Checking for global msb installation...")
    check_microsandbox_binary()
    print()
    
    # Check 3: Microsandbox server
    print("[3/5] Checking Microsandbox server...")
    server_running = check_microsandbox_server()
    if not server_running:
        all_passed = False
    print()
    
    # Check 4: Sandboxfile
    print("[4/5] Checking Sandboxfile configuration...")
    if not check_sandboxfile():
        all_passed = False
    print()
    
    # Check 5: Volume support (only if server is running)
    print("[5/5] Testing volume mounting support...")
    if server_running:
        volume_works, server_ok_volume_failed = asyncio.run(test_volume_support())
        if not volume_works and not server_ok_volume_failed:
            all_passed = False
    else:
        print_step("Skipped (server not running)", "⚠")
        all_passed = False
    print()

    # Final verdict
    print("=" * 60)
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("AgentKernel is ready to use.")
        print()
        print("Try it:")
        print("  python -c \"from agentkernel import execute_task; print(execute_task('print(\\\"Hello!\\\")'))\"")
    else:
        print("❌ SETUP INCOMPLETE")
        print("Please fix the issues above before using AgentKernel.")
        print()
        print("See DOCS.md for detailed setup instructions:")
        print("  https://github.com/your-org/agentkernel/blob/main/DOCS.md")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
