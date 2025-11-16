#!/usr/bin/env python3
"""Check if all required packages are installed for running examples."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_package(name: str, import_name: str = None) -> tuple[bool, str]:
    """Check if a package is installed."""
    if import_name is None:
        import_name = name
    try:
        __import__(import_name)
        return True, f"✅ {name}"
    except ImportError as e:
        return False, f"❌ {name}: {e}"

def main():
    """Check all required packages."""
    print("=" * 60)
    print("Checking required packages for examples...")
    print("=" * 60)
    print()
    
    required_packages = [
        ("fastmcp", "fastmcp"),
        ("microsandbox", "microsandbox"),
        ("pydantic", "pydantic"),
        ("pyyaml", "yaml"),
        ("typing-extensions", "typing_extensions"),
        ("python-dotenv", "dotenv"),
        ("openai", "openai"),
        ("sentence-transformers", "sentence_transformers"),
        ("numpy", "numpy"),
    ]
    
    missing = []
    for pkg_name, import_name in required_packages:
        installed, message = check_package(pkg_name, import_name)
        print(message)
        if not installed:
            missing.append(pkg_name)
    
    print()
    print("=" * 60)
    print("Checking project modules...")
    print("=" * 60)
    print()
    
    project_modules = [
        ("client.agent_helper", "AgentHelper"),
        ("client.filesystem_helpers", "FilesystemHelper"),
        ("client.sandbox_executor", "SandboxExecutor"),
        ("config.loader", "load_config"),
    ]
    
    for module_name, class_name in project_modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✅ {module_name}.{class_name}")
        except (ImportError, AttributeError) as e:
            print(f"❌ {module_name}.{class_name}: {e}")
            missing.append(f"{module_name}.{class_name}")
    
    print()
    print("=" * 60)
    print("Checking filesystem structure...")
    print("=" * 60)
    print()
    
    from config.loader import load_config
    config = load_config()
    
    from pathlib import Path
    servers_dir = Path(config.execution.servers_dir)
    workspace_dir = Path(config.execution.workspace_dir)
    skills_dir = Path(config.execution.skills_dir)
    
    print(f"Servers directory: {servers_dir.resolve()}")
    print(f"  Exists: {servers_dir.exists()}")
    if servers_dir.exists():
        servers = [d.name for d in servers_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]
        print(f"  Servers found: {len(servers)} - {servers}")
    
    print(f"\nWorkspace directory: {workspace_dir.resolve()}")
    print(f"  Exists: {workspace_dir.exists()}")
    
    print(f"\nSkills directory: {skills_dir.resolve()}")
    print(f"  Exists: {skills_dir.exists()}")
    
    print()
    print("=" * 60)
    if missing:
        print(f"❌ Setup incomplete: {len(missing)} issue(s) found")
        print("\nMissing packages:")
        for item in missing:
            if "." not in item:  # It's a package, not a module
                print(f"  pip install {item}")
        return 1
    else:
        print("✅ All checks passed! Examples should work.")
        return 0

if __name__ == "__main__":
    sys.exit(main())

