import pytest
from mcpruntime.replay_log import log_execution, load_session, list_sessions

@pytest.fixture
def override_log_dir(tmp_path):
    log_dir = tmp_path / ".replay"
    return log_dir

def test_log_and_load_session(override_log_dir):
    session_id = "test-session-123"
    entry1 = {"task": "Task 1", "code": "print(1)", "output": "1", "success": True}
    entry2 = {"task": "Task 2", "code": "print(2)", "output": "2", "success": True}
    
    log_execution(session_id, entry1, log_dir=override_log_dir)
    log_execution(session_id, entry2, log_dir=override_log_dir)
    
    loaded = load_session(session_id, log_dir=override_log_dir)
    assert len(loaded) == 2
    assert loaded[0]["task"] == "Task 1"
    assert "timestamp" in loaded[0]
    
    sessions = list_sessions(log_dir=override_log_dir)
    assert session_id in sessions

def test_load_nonexistent_session(override_log_dir):
    with pytest.raises(FileNotFoundError):
        load_session("does_not_exist", log_dir=override_log_dir)
