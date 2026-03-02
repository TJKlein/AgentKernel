#!/usr/bin/env python3
"""Run test with detailed logging to file."""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# Setup logging to file
log_file = Path("/tmp/test_run.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Project root (parent of scripts/)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

logger.info("=" * 60)
logger.info("Starting Test with Logging")
logger.info("=" * 60)

try:
    from microsandbox import PythonSandbox
    logger.info("✅ microsandbox imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import microsandbox: {e}")
    sys.exit(1)

async def test():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)
    
    logger.info(f"📁 Workspace: {workspace}")
    logger.info("🚀 Creating sandbox with volume mount...")
    
    try:
        async with PythonSandbox.create(
            name="test-with-logging",
            volumes=[(str(workspace), "/workspace")]
        ) as sandbox:
            logger.info("✅ Sandbox created")
            
            # Test code with detailed tracing
            code = '''
import os
import sys

print("=== TEST CODE START ===", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Current working directory: {os.getcwd()}", flush=True)
print(f"sys.path: {sys.path}", flush=True)
print("", flush=True)

print("=== VOLUME MOUNT CHECK ===", flush=True)
workspace_exists = os.path.exists('/workspace')
workspace_isdir = os.path.isdir('/workspace') if workspace_exists else False
print(f"/workspace exists: {workspace_exists}", flush=True)
print(f"/workspace is directory: {workspace_isdir}", flush=True)

if workspace_exists:
    try:
        contents = os.listdir('/workspace')
        print(f"/workspace contents: {contents}", flush=True)
    except Exception as e:
        print(f"Error listing /workspace: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
    
    # Test writing
    print("", flush=True)
    print("=== TEST FILE WRITE ===", flush=True)
    try:
        test_file = '/workspace/test_with_logging.txt'
        test_content = f'Test at {__import__("datetime").datetime.now()}'
        print(f"Writing to: {test_file}", flush=True)
        print(f"Content: {test_content}", flush=True)
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        print(f"File written. Exists: {os.path.exists(test_file)}", flush=True)
        
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                read_back = f.read()
            print(f"Read back: {read_back}", flush=True)
            print("✅ File write test PASSED", flush=True)
        else:
            print("❌ File write test FAILED - file not found after write", flush=True)
            
    except Exception as e:
        print(f"❌ Error writing file: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
else:
    print("❌ /workspace does not exist - volume mount may have failed", flush=True)

print("", flush=True)
print("=== TEST CODE END ===", flush=True)
'''
            
            logger.info("📝 Running test code in sandbox...")
            result = await sandbox.run(code)
            output = await result.output()
            
            logger.info("\n=== SANDBOX OUTPUT ===")
            logger.info(output)
            
            # Check stderr
            try:
                stderr = await result.error()
                if stderr:
                    logger.info("\n=== STDERR OUTPUT ===")
                    logger.info(stderr)
            except:
                pass
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
    # Check if file was created
    logger.info("\n=== CHECKING HOST FILESYSTEM ===")
    test_file = workspace / "test_with_logging.txt"
    if test_file.exists():
        content = test_file.read_text()
        logger.info(f"✅ File found: {test_file}")
        logger.info(f"   Content: {content}")
        return True
    else:
        logger.warning(f"❌ File not found: {test_file}")
        logger.info(f"   Workspace contents: {list(workspace.iterdir())}")
        return False

if __name__ == "__main__":
    logger.info("Starting async test...")
    success = asyncio.run(test())
    logger.info("")
    logger.info("=" * 60)
    if success:
        logger.info("✅ TEST PASSED")
    else:
        logger.info("❌ TEST FAILED")
    logger.info("=" * 60)
    logger.info(f"Full log saved to: {log_file}")
    sys.exit(0 if success else 1)

