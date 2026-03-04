import pytest
import asyncio
from client.base import CodeExecutor, ExecutionResult, ValidationResult
from mcpruntime.streaming import StreamingExecutor

class DummyExecutor(CodeExecutor):
    def execute(self, code, context=None):
        return ExecutionResult.SUCCESS, "line1\nline2\nline3\n", None
    
    def validate_code(self, code):
        return ValidationResult(valid=True, errors=[], warnings=[])

@pytest.mark.asyncio
async def test_streaming_executor():
    dummy = DummyExecutor()
    streamer = StreamingExecutor(dummy)
    
    chunks = []
    async for chunk in streamer.execute_streaming("print('test')"):
        chunks.append(chunk)
        
    print("CHUNKS ACTUALLY PRODUCED:", chunks)
    assert len(chunks) == 4
    assert chunks[0] == {"type": "stdout", "data": "line1\n"}
    assert chunks[1] == {"type": "stdout", "data": "line2\n"}
    assert chunks[2] == {"type": "stdout", "data": "line3\n"}
    assert chunks[3] == {"type": "done", "returncode": 0}

@pytest.mark.asyncio
async def test_streaming_executor_error():
    class ErrorExecutor(CodeExecutor):
        def execute(self, code, context=None):
            return ExecutionResult.FAILURE, None, "Compile Error"
        
        def validate_code(self, code):
            return ValidationResult(valid=True, errors=[], warnings=[])

    dummy = ErrorExecutor()
    streamer = StreamingExecutor(dummy)
    
    chunks = []
    async for chunk in streamer.execute_streaming("bad code"):
        chunks.append(chunk)
        
    assert len(chunks) == 2
    assert chunks[0] == {"type": "error", "data": "Compile Error"}
    assert chunks[1] == {"type": "done", "returncode": 1}
