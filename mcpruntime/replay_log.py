import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_LOG_DIR = Path("workspace/.replay")

def log_execution(session_id: str, entry: Dict[str, Any], log_dir: Optional[Path] = None) -> None:
    """Log an execution step to the session's replay log."""
    actual_log_dir = log_dir or DEFAULT_LOG_DIR
    actual_log_dir.mkdir(parents=True, exist_ok=True)
    path = actual_log_dir / f"{session_id}.jsonl"
    entry["timestamp"] = time.time()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def load_session(session_id: str, log_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load all executed steps from a session for replay."""
    actual_log_dir = log_dir or DEFAULT_LOG_DIR
    path = actual_log_dir / f"{session_id}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No session found: {session_id}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def list_sessions(log_dir: Optional[Path] = None) -> List[str]:
    """List all available replay session IDs."""
    actual_log_dir = log_dir or DEFAULT_LOG_DIR
    if not actual_log_dir.exists():
        return []
    # Sort sessions by modification time (newest first)
    sessions = [(p.stat().st_mtime, p.stem) for p in actual_log_dir.glob("*.jsonl")]
    sessions.sort(reverse=True)
    return [s[1] for s in sessions]
