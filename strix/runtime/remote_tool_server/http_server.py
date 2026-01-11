"""FastAPI server for remote tool execution (Cloudflared-compatible).

This replaces the low-level http.server with a modern FastAPI implementation
that offers better performance, validation, and async support.
"""

import logging
import os
import signal
import sys
import time
from typing import Any, List, Optional

from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from .tool_executor import ToolExecutor
from .metrics import get_metrics

logger = logging.getLogger(__name__)

# Server configuration
SERVER_PORT = int(os.getenv("STRIX_SERVER_PORT", "50051"))
AUTH_TOKEN = os.getenv("STRIX_SERVER_TOKEN", "")
TOOL_POOL_SIZE = int(os.getenv("STRIX_TOOL_POOL_SIZE", "10"))

# Registered agents
_registered_agents: set[str] = set()
_tool_executor: Optional[ToolExecutor] = None

def get_tool_executor() -> ToolExecutor:
    """Get or create tool executor instance."""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ToolExecutor(pool_size=TOOL_POOL_SIZE)
    return _tool_executor

# --- Models ---

class ExecuteRequest(BaseModel):
    agent_id: str = "unknown"
    tool_name: str
    kwargs: dict = Field(default_factory=dict)
    timeout: Optional[float] = None
    auth_token: Optional[str] = None

class ExecuteResponse(BaseModel):
    success: bool
    result: Any = None
    error: str = ""
    exit_code: int

class ToolSpec(BaseModel):
    tool_name: str
    kwargs: dict = Field(default_factory=dict)

class BatchExecuteRequest(BaseModel):
    agent_id: str = "unknown"
    tools: List[ToolSpec]
    auth_token: Optional[str] = None

class BatchExecuteResponse(BaseModel):
    results: List[ExecuteResponse]

class RegisterAgentRequest(BaseModel):
    agent_id: str
    auth_token: Optional[str] = None

class RegisterAgentResponse(BaseModel):
    success: bool
    agent_id: str
    message: str

# --- FastAPI App Setup ---

app = FastAPI(
    title="Strix Tool Server",
    description="Remote execution server for Strix tools",
    version="1.0.0-fastapi"
)

# CORS middleware for potential web UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- Authentication ---

def verify_auth(request: Request, body: Optional[dict] = None):
    """Verify authentication via header or body."""
    if not AUTH_TOKEN:
        return True
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token == AUTH_TOKEN:
            return True
    
    # Check body for auth_token if header fails
    if body and body.get("auth_token") == AUTH_TOKEN:
        return True
    
    raise HTTPException(status_code=401, detail="Unauthorized")

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Strix Tool Server is running"}

@app.post("/execute", response_model=ExecuteResponse)
def execute_tool_endpoint(request: Request, body: ExecuteRequest):
    """Execute a single tool."""
    logger.info(f"Received execute request for tool: {body.tool_name}")
    verify_auth(request, body.model_dump())
    
    exec_start = time.time()
    try:
        executor = get_tool_executor()
        result = executor.execute_tool(
            body.tool_name, 
            body.kwargs, 
            timeout=body.timeout
        )
        
        exec_duration = time.time() - exec_start
        metrics = get_metrics()
        metrics.record_tool_execution(
            body.tool_name, 
            exec_duration, 
            "error" not in result
        )
        
        if "error" in result:
            return ExecuteResponse(
                success=False,
                error=result["error"],
                result=None,
                exit_code=1
            )
        else:
            return ExecuteResponse(
                success=True,
                result=result.get("result"),
                error="",
                exit_code=0
            )
            
    except Exception as e:
        logger.exception(f"Error executing tool {body.tool_name}: {e}")
        return ExecuteResponse(
            success=False,
            error=str(e),
            result=None,
            exit_code=1
        )

@app.post("/execute_batch", response_model=BatchExecuteResponse)
def execute_batch_endpoint(request: Request, body: BatchExecuteRequest):
    """Execute multiple tools in batch."""
    verify_auth(request, body.model_dump())
    
    if not body.tools:
        raise HTTPException(status_code=400, detail="tools list is required")
    
    try:
        executor = get_tool_executor()
        
        # Convert internal tool specs
        tool_specs = [
            {"tool_name": t.tool_name, "kwargs": t.kwargs} 
            for t in body.tools
        ]
        
        results = executor.execute_batch(tool_specs)
        
        formatted_results = []
        for res in results:
            if "error" in res:
                formatted_results.append(ExecuteResponse(
                    success=False,
                    error=res["error"],
                    exit_code=1
                ))
            else:
                formatted_results.append(ExecuteResponse(
                    success=True,
                    result=res.get("result"),
                    exit_code=0
                ))
        
        return BatchExecuteResponse(results=formatted_results)
        
    except Exception as e:
        logger.exception(f"Error executing batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/register_agent", response_model=RegisterAgentResponse)
def register_agent_endpoint(request: Request, body: RegisterAgentRequest):
    """Register an agent with the server."""
    verify_auth(request, body.model_dump())
    
    _registered_agents.add(body.agent_id)
    return RegisterAgentResponse(
        success=True,
        agent_id=body.agent_id,
        message=f"Agent {body.agent_id} registered successfully"
    )

@app.get("/health")
@app.post("/health") # Support both GET and POST for health check
def health_check():
    """Health check endpoint."""
    logger.info("Received health check request")
    from strix.tools.registry import get_tool_names
    
    try:
        metrics = get_metrics()
        server_stats = metrics.get_server_stats()
    except Exception:
        server_stats = {}

    return {
        "healthy": True,
        "version": "1.0.0-fastapi",
        "registered_agents": len(_registered_agents),
        "tool_count": len(get_tool_names()),
        "network_status": "unknown (check disabled)",
        "metrics": {
            "uptime_seconds": server_stats.get("uptime_seconds", 0),
            "request_rate": server_stats.get("request_rate_per_minute", 0),
            "error_rate": server_stats.get("error_rate", 0),
            "total_requests": server_stats.get("total_requests", 0),
        },
    }

# --- Server Start ---

def serve() -> None:
    """Start the FastAPI server using Uvicorn."""
    if not AUTH_TOKEN:
        logger.warning("STRIX_SERVER_TOKEN not set. Server will run without authentication!")
    
    logger.info("Initializing tools...")
    try:
        import strix.tools # noqa: F401
        from strix.tools.registry import get_tool_names
        tool_count = len(get_tool_names())
        logger.info(f"Initialized {tool_count} tools")
    except Exception as e:
        logger.warning(f"Tool initialization warning: {e}")
    
    logger.info(f"Starting Strix FastAPI Tool Server on port {SERVER_PORT}")
    logger.info(f"Tool pool size: {TOOL_POOL_SIZE}")
    logger.info(f"Authentication: {'Enabled' if AUTH_TOKEN else 'Disabled (WARNING!)'}")
    
    # Configure uvicorn
    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=SERVER_PORT, 
        log_level="info",
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("Shutting down server...")
        executor = get_tool_executor()
        if executor:
            executor.shutdown()
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        server.run()
    except Exception as e:
        logger.exception(f"Fatal error in server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    serve()
