import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from mcpruntime import create_agent
from mcpruntime.streaming import StreamingExecutor

app = FastAPI(title="MCPRuntime Streaming API")

class ExecuteRequest(BaseModel):
    code: str
    sandbox_type: Optional[str] = None

@app.post("/execute/stream")
async def execute_stream(request: ExecuteRequest):
    # Initialize the agent logic
    agent = create_agent()
    
    # Wrap in our streaming executor
    streaming_executor = StreamingExecutor(agent.executor)
    
    async def event_generator():
        async for chunk in streaming_executor.execute_streaming(request.code):
            yield f"data: {json.dumps(chunk)}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.http_server:app", host="0.0.0.0", port=8000, reload=True)
