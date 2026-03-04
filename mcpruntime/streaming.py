import asyncio
from typing import AsyncGenerator, Dict, Any, Optional

from client.base import CodeExecutor, ExecutionResult

class StreamingExecutor:
    """A wrapper for CodeExecutor that captures stdout and streams it.
    
    Since the underlying execution backends currently return output all at once,
    this wrapper simulates streaming for UI demonstration purposes by yielding
    the text line-by-line.
    """

    def __init__(self, executor: CodeExecutor):
        self.executor = executor

    async def execute_streaming(
        self, code: str, context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        loop = asyncio.get_event_loop()
        try:
            # We run the synchronous execute method in a background thread
            result, output, error = await loop.run_in_executor(
                None, self.executor.execute, code, context
            )
            
            if output:
                # Simulate streaming the output line by line
                for line in str(output).splitlines(keepends=True):
                    yield {"type": "stdout", "data": line}
                    await asyncio.sleep(0.05)  # Simulate real-time streaming delay for demo
                    
            if error:
                yield {"type": "error", "data": str(error)}
                
            yield {"type": "done", "returncode": 0 if result == ExecutionResult.SUCCESS else 1}
            
        except Exception as e:
            yield {"type": "error", "data": str(e)}
            yield {"type": "done", "returncode": 1}
