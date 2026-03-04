"""Example 18: Streaming Execution Output

This example demonstrates how to consume the Server-Sent Events (SSE) streaming API 
from an MCPRuntime server.

Prerequisites:
  1. Start the HTTP server in another terminal:
     python -m server.http_server

  2. Run this script:
     python examples/18_streaming.py
"""

import sys
import json
import httpx

def main():
    print("=" * 60)
    print("Example 18: Streaming Execution Output via SSE")
    print("=" * 60)
    print("Connecting to http://localhost:8000/execute/stream ...\n")

    code = """
import time
print("Starting long-running data processing task...")
for i in range(1, 10):
    print(f"[{i}/9] Processing data batch {i}...")
    time.sleep(0.3)
print("Task completed successfully!")
"""

    try:
        with httpx.stream("POST", "http://localhost:8000/execute/stream", json={"code": code}, timeout=30.0) as r:
            # Check if server is reachable and returned 200 OK
            r.raise_for_status()
            
            for line in r.iter_lines():
                if line.startswith("data: "):
                    # Parse the JSON payload inside the SSE message
                    chunk = json.loads(line[6:])
                    
                    if chunk["type"] == "stdout":
                        print(chunk["data"], end="", flush=True)
                    elif chunk["type"] == "error":
                        print(f"\n[ERROR] {chunk['data']}", file=sys.stderr)
                    elif chunk["type"] == "done":
                        print(f"\n\n[DONE] Process exited with returncode: {chunk['returncode']}")
    except httpx.ConnectError:
        print("❌ Could not connect to the streaming server.")
        print("   Did you forget to start it? Run: python -m server.http_server")
    except Exception as e:
        print(f"\nAn error occurred: {e}")


if __name__ == "__main__":
    main()
