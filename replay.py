#!/usr/bin/env python3
import sys
import json
from mcpruntime.replay_log import load_session, list_sessions

def main():
    if len(sys.argv) < 2 or sys.argv[1] == "list":
        sessions = list_sessions()
        print(f"Found {len(sessions)} sessions (newest first):")
        for s in sessions:
            print(f"  {s}")
        return

    session_id = sys.argv[1]
    step = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    try:
        entries = load_session(session_id)
    except FileNotFoundError as e:
        print(e)
        return

    if step is not None:
        entries = entries[:step]
        print(f"--- Replaying session {session_id} up to step {step} ---")
    else:
        print(f"--- Full session {session_id} ({len(entries)} steps) ---")

    for i, entry in enumerate(entries):
        print(f"\n[Step {i+1}] {entry['task']}")
        code_preview = entry['code'][:120].replace('\n', ' ') + "..." if len(entry['code']) > 120 else entry['code'].replace('\n', ' ')
        print(f"  Code: {code_preview}")
        out_preview = entry['output'][:200].replace('\n', ' ') + "..." if len(entry['output']) > 200 else entry['output'].replace('\n', ' ')
        print(f"  Output: {out_preview}")
        print(f"  Success: {entry['success']}")

if __name__ == "__main__":
    main()
