"""Concurrent Tool Server for Strix Sandbox.

This server runs inside the sandbox container and handles tool execution requests
from the main Strix process. It supports true concurrent execution of multiple
tools simultaneously using a thread pool executor.

PERFORMANCE OPTIMIZATIONS (v2):
- Replaced single-worker process queue with ThreadPoolExecutor
- Supports concurrent tool execution (configurable pool size)
- Reduced latency with direct async execution
- Better resource utilization for parallel tool calls

NETWORKING (v2.1):
- Added network connectivity diagnostics
- Better error messages for network issues
- Health check includes network status

Environment Variables:
- STRIX_TOOL_EXECUTION_TIMEOUT: Timeout per tool execution (default: 60s)
- STRIX_TOOL_POOL_SIZE: Number of concurrent tool workers (default: 10)
- STRIX_SANDBOX_MODE: Must be "true" for this server to run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError


SANDBOX_MODE = os.getenv("STRIX_SANDBOX_MODE", "false").lower() == "true"
# Timeout for tool execution in seconds (default: 60s, can be overridden)
TOOL_EXECUTION_TIMEOUT = float(os.getenv("STRIX_TOOL_EXECUTION_TIMEOUT", "60"))
# Number of concurrent tool workers (default: 10 for high parallelism)
TOOL_POOL_SIZE = int(os.getenv("STRIX_TOOL_POOL_SIZE", "10"))

if not SANDBOX_MODE:
    raise RuntimeError("Tool server should only run in sandbox mode (STRIX_SANDBOX_MODE=true)")

parser = argparse.ArgumentParser(description="Start Strix tool server")
parser.add_argument("--token", required=True, help="Authentication token")
parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")  # nosec
parser.add_argument("--port", type=int, required=True, help="Port to bind to")

args = parser.parse_args()
EXPECTED_TOKEN = args.token

app = FastAPI(title="Strix Tool Server", version="2.0.0")
security = HTTPBearer()
security_dependency = Depends(security)

# Global thread pool for concurrent tool execution
_tool_executor: ThreadPoolExecutor | None = None
_registered_agents: set[str] = set()

# Pre-import tool modules for faster execution
_tools_initialized = False


def _initialize_tools() -> None:
    """Pre-import tool modules for faster execution."""
    global _tools_initialized
    if _tools_initialized:
        return
    
    try:
        # Import tool registry to ensure all tools are loaded
        from strix.tools.registry import get_tool_names
        tool_count = len(get_tool_names())
        logging.getLogger(__name__).info(f"Initialized {tool_count} tools in tool server")
        _tools_initialized = True
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to pre-initialize tools: {e}")


def get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor."""
    global _tool_executor
    if _tool_executor is None:
        _tool_executor = ThreadPoolExecutor(
            max_workers=TOOL_POOL_SIZE,
            thread_name_prefix="strix-tool-"
        )
        logging.getLogger(__name__).info(
            f"Created tool executor with {TOOL_POOL_SIZE} workers"
        )
    return _tool_executor


def verify_token(credentials: HTTPAuthorizationCredentials) -> str:
    """Verify the authentication token."""
    if not credentials or credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != EXPECTED_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


class ToolExecutionRequest(BaseModel):
    """Request model for tool execution."""
    agent_id: str
    tool_name: str
    kwargs: dict[str, Any]


class ToolExecutionResponse(BaseModel):
    """Response model for tool execution."""
    result: Any | None = None
    error: str | None = None


class BatchToolExecutionRequest(BaseModel):
    """Request model for batch tool execution (multiple tools at once)."""
    agent_id: str
    tools: list[dict[str, Any]]  # Each item has tool_name and kwargs


class BatchToolExecutionResponse(BaseModel):
    """Response model for batch tool execution."""
    results: list[ToolExecutionResponse]


def _execute_tool_sync(tool_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Synchronously execute a tool (runs in thread pool).
    
    This function is designed to be run in a thread pool executor for
    concurrent execution of multiple tools.
    """
    try:
        from strix.tools.argument_parser import ArgumentConversionError, convert_arguments
        from strix.tools.registry import get_tool_by_name

        tool_func = get_tool_by_name(tool_name)
        if not tool_func:
            return {"error": f"Tool '{tool_name}' not found"}

        converted_kwargs = convert_arguments(tool_func, kwargs)
        result = tool_func(**converted_kwargs)

        return {"result": result}

    except (ArgumentConversionError, ValidationError) as e:
        return {"error": f"Invalid arguments: {e}"}
    except Exception as e:
        # Catch all exceptions to prevent thread crashes
        return {"error": f"Tool execution error: {type(e).__name__}: {str(e)}"}


@app.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    credentials: HTTPAuthorizationCredentials = security_dependency
) -> ToolExecutionResponse:
    """Execute a single tool.
    
    This endpoint supports concurrent execution - multiple requests can be
    processed simultaneously through the thread pool.
    """
    verify_token(credentials)
    
    # Ensure tools are initialized
    _initialize_tools()
    
    executor = get_executor()
    loop = asyncio.get_event_loop()

    try:
        # Execute tool in thread pool with timeout
        response = await asyncio.wait_for(
            loop.run_in_executor(
                executor,
                _execute_tool_sync,
                request.tool_name,
                request.kwargs
            ),
            timeout=TOOL_EXECUTION_TIMEOUT
        )

        if "error" in response:
            return ToolExecutionResponse(error=response["error"])
        return ToolExecutionResponse(result=response.get("result"))

    except asyncio.TimeoutError:
        return ToolExecutionResponse(
            error=f"Tool execution timed out after {TOOL_EXECUTION_TIMEOUT}s. "
                  f"The tool '{request.tool_name}' may be hanging or taking too long."
        )
    except Exception as e:
        return ToolExecutionResponse(error=f"Execution error: {type(e).__name__}: {str(e)}")


@app.post("/execute_batch", response_model=BatchToolExecutionResponse)
async def execute_tools_batch(
    request: BatchToolExecutionRequest,
    credentials: HTTPAuthorizationCredentials = security_dependency
) -> BatchToolExecutionResponse:
    """Execute multiple tools concurrently.
    
    This endpoint enables true parallel execution of multiple tools,
    significantly improving throughput for multi-action agent calls.
    
    Example request:
    {
        "agent_id": "agent-123",
        "tools": [
            {"tool_name": "click", "kwargs": {"element": "button"}},
            {"tool_name": "type_text", "kwargs": {"text": "hello"}},
            {"tool_name": "screenshot", "kwargs": {}}
        ]
    }
    """
    verify_token(credentials)
    
    # Ensure tools are initialized
    _initialize_tools()
    
    if not request.tools:
        return BatchToolExecutionResponse(results=[])
    
    executor = get_executor()
    loop = asyncio.get_event_loop()
    
    # Create tasks for all tools
    tasks = []
    for tool_spec in request.tools:
        tool_name = tool_spec.get("tool_name", "")
        kwargs = tool_spec.get("kwargs", {})
        
        task = loop.run_in_executor(
            executor,
            _execute_tool_sync,
            tool_name,
            kwargs
        )
        tasks.append(task)
    
    # Execute all tools concurrently with overall timeout
    overall_timeout = TOOL_EXECUTION_TIMEOUT * 2  # Allow more time for batches
    
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=overall_timeout
        )
        
        # Convert results to response format
        responses = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                responses.append(ToolExecutionResponse(
                    error=f"Tool execution error: {type(result).__name__}: {str(result)}"
                ))
            elif isinstance(result, dict):
                if "error" in result:
                    responses.append(ToolExecutionResponse(error=result["error"]))
                else:
                    responses.append(ToolExecutionResponse(result=result.get("result")))
            else:
                responses.append(ToolExecutionResponse(error="Unexpected result type"))
        
        return BatchToolExecutionResponse(results=responses)
        
    except asyncio.TimeoutError:
        return BatchToolExecutionResponse(results=[
            ToolExecutionResponse(error=f"Batch execution timed out after {overall_timeout}s")
        ])


@app.post("/register_agent")
async def register_agent(
    agent_id: str,
    credentials: HTTPAuthorizationCredentials = security_dependency
) -> dict[str, str]:
    """Register an agent with the tool server.
    
    This is now a lightweight operation since we don't create per-agent
    worker processes anymore.
    """
    verify_token(credentials)
    
    # Initialize tools on first agent registration
    _initialize_tools()
    
    _registered_agents.add(agent_id)
    return {"status": "registered", "agent_id": agent_id}


def _check_network_connectivity() -> dict[str, Any]:
    """Check network connectivity from inside the sandbox container."""
    import socket
    import subprocess
    
    network_status = {
        "dns_resolution": False,
        "external_connectivity": False,
        "localhost_accessible": True,  # Assume true if we're running
        "issues": [],
    }
    
    # Check DNS resolution
    try:
        socket.gethostbyname("google.com")
        network_status["dns_resolution"] = True
    except socket.gaierror as e:
        network_status["issues"].append(f"DNS resolution failed: {e}")
    
    # Check external connectivity
    try:
        # Try to connect to a known public IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(("8.8.8.8", 53))  # Google DNS
        if result == 0:
            network_status["external_connectivity"] = True
        sock.close()
    except (socket.error, OSError) as e:
        network_status["issues"].append(f"External connectivity failed: {e}")
    
    # Check if we can resolve the host gateway (for reaching host services)
    try:
        socket.gethostbyname("host.docker.internal")
        network_status["host_gateway_available"] = True
    except socket.gaierror:
        network_status["host_gateway_available"] = False
        # Not an error in host network mode
    
    return network_status


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint with network diagnostics."""
    executor = get_executor()
    
    # Check network connectivity
    network_status = _check_network_connectivity()
    
    return {
        "status": "healthy",
        "version": "2.1.0",  # Updated version with network diagnostics
        "sandbox_mode": str(SANDBOX_MODE),
        "environment": "sandbox" if SANDBOX_MODE else "main",
        "auth_configured": "true" if EXPECTED_TOKEN else "false",
        "pool_size": TOOL_POOL_SIZE,
        "tool_timeout": TOOL_EXECUTION_TIMEOUT,
        "registered_agents": len(_registered_agents),
        "agents": list(_registered_agents),
        "tools_initialized": _tools_initialized,
        "network": network_status,
    }


@app.get("/stats")
async def get_stats(
    credentials: HTTPAuthorizationCredentials = security_dependency
) -> dict[str, Any]:
    """Get execution statistics."""
    verify_token(credentials)
    
    return {
        "pool_size": TOOL_POOL_SIZE,
        "tool_timeout": TOOL_EXECUTION_TIMEOUT,
        "registered_agents": len(_registered_agents),
        "tools_initialized": _tools_initialized,
    }


def cleanup() -> None:
    """Cleanup resources on shutdown."""
    global _tool_executor
    
    if _tool_executor is not None:
        logging.getLogger(__name__).info("Shutting down tool executor...")
        _tool_executor.shutdown(wait=True, cancel_futures=True)
        _tool_executor = None
    
    logging.getLogger(__name__).info("Tool server cleanup complete")


def signal_handler(_signum: int, _frame: Any) -> None:
    """Handle shutdown signals."""
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    cleanup()
    sys.exit(0)


# Setup signal handlers
if hasattr(signal, "SIGPIPE"):
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    try:
        logging.getLogger(__name__).info(
            f"Starting Strix Tool Server v2.0.0 (concurrent) on {args.host}:{args.port}"
        )
        logging.getLogger(__name__).info(
            f"Pool size: {TOOL_POOL_SIZE}, Timeout: {TOOL_EXECUTION_TIMEOUT}s"
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        cleanup()
