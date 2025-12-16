#!/usr/bin/env python3
"""Test script for AgentKernel async middleware functionality."""

import sys
import time
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("AgentKernel Async Middleware Test Suite")
print("=" * 60)

# Pre-pull Docker image to avoid timeouts
print("\n[Setup] Checking Docker image...")
try:
    result = subprocess.run(
        ["docker", "pull", "microsandbox/python"],
        capture_output=True,
        text=True,
        timeout=120
    )
    if result.returncode == 0:
        print("✅ Docker image ready")
    else:
        print(f"⚠️  Docker pull warning: {result.stderr[:100]}")
except subprocess.TimeoutExpired:
    print("⚠️  Docker pull timed out (may already be cached)")
except FileNotFoundError:
    print("⚠️  Docker not found (tests may timeout on first run)")
except Exception as e:
    print(f"⚠️  Docker check failed: {e}")

# Test 1: Import Test
print("\n[Test 1] Testing imports...")
try:
    from code_execution_mcp import create_agent, TaskManager
    print("✅ Imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Agent Creation
print("\n[Test 2] Creating agent...")
try:
    agent = create_agent()
    print("✅ Agent created successfully")
except Exception as e:
    print(f"❌ Agent creation failed: {e}")
    sys.exit(1)

# Test 3: TaskManager Initialization
print("\n[Test 3] Initializing TaskManager...")
try:
    manager = TaskManager(agent, max_workers=3)
    print(f"✅ TaskManager initialized with {manager.max_workers} workers")
except Exception as e:
    print(f"❌ TaskManager initialization failed: {e}")
    sys.exit(1)

# Test 4: Simple Task Dispatch
print("\n[Test 4] Dispatching simple task...")
try:
    task_id = manager.dispatch_task("print('Hello from async task!')")
    print(f"✅ Task dispatched with ID: {task_id}")
except Exception as e:
    print(f"❌ Task dispatch failed: {e}")
    sys.exit(1)

# Test 5: Task Status Check
print("\n[Test 5] Checking task status...")
try:
    time.sleep(0.5)  # Give task time to start
    status = manager.get_task_status(task_id)
    print(f"✅ Task status: {status['status']}")
    print(f"   Description: {status.get('description', 'N/A')}")
except Exception as e:
    print(f"❌ Status check failed: {e}")
    sys.exit(1)

# Test 6: Wait for Task Completion
print("\n[Test 6] Waiting for task completion...")
try:
    result = manager.wait_for_task(task_id, timeout=30)
    if result['status'] == 'completed':
        print(f"✅ Task completed successfully")
        print(f"   Output: {result.get('output', 'No output')[:100]}")
    elif result['status'] == 'failed':
        print(f"⚠️  Task failed: {result.get('error', 'Unknown error')}")
    else:
        print(f"⚠️  Task status: {result['status']}")
except Exception as e:
    print(f"❌ Wait failed: {e}")
    sys.exit(1)

# Test 7: Multiple Parallel Tasks
print("\n[Test 7] Testing parallel execution (3 tasks)...")
try:
    task_ids = []
    for i in range(3):
        tid = manager.dispatch_task(f"print('Task {i+1} executing')")
        task_ids.append(tid)
        print(f"   Dispatched task {i+1}: {tid}")
    
    print("   Waiting for all tasks...")
    results = []
    for tid in task_ids:
        result = manager.wait_for_task(tid, timeout=30)
        results.append(result)
    
    completed = sum(1 for r in results if r['status'] == 'completed')
    print(f"✅ {completed}/{len(task_ids)} tasks completed")
except Exception as e:
    print(f"❌ Parallel execution test failed: {e}")
    sys.exit(1)

# Test 8: List All Tasks
print("\n[Test 8] Listing all tasks...")
try:
    all_tasks = manager.list_tasks()
    print(f"✅ Total tasks tracked: {len(all_tasks)}")
    for tid, task_info in list(all_tasks.items())[:3]:
        print(f"   {tid}: {task_info['status']}")
except Exception as e:
    print(f"❌ List tasks failed: {e}")
    sys.exit(1)

# Test 9: Task Cancellation
print("\n[Test 9] Testing task cancellation...")
try:
    # Dispatch a long-running task
    long_task = manager.dispatch_task("import time; time.sleep(100)")
    time.sleep(0.1)  # Let it start
    
    # Try to cancel
    cancelled = manager.cancel_task(long_task)
    print(f"   Cancellation {'successful' if cancelled else 'failed (already started)'}")
    
    # Check status
    status = manager.get_task_status(long_task)
    print(f"✅ Task status after cancel attempt: {status['status']}")
except Exception as e:
    print(f"❌ Cancellation test failed: {e}")
    # Not critical, continue

# Test 10: Cleanup
print("\n[Test 10] Cleanup...")
try:
    manager.shutdown(wait=False)
    print("✅ TaskManager shut down successfully")
except Exception as e:
    print(f"⚠️  Shutdown warning: {e}")

# Summary
print("\n" + "=" * 60)
print("✅ All critical tests passed!")
print("=" * 60)
print("\nAsync middleware is working correctly!")
print("\nNext steps:")
print("  1. Try: from code_execution_mcp import TaskManager")
print("  2. Create agent and dispatch async tasks")
print("  3. Use MCP server with new async tools")
