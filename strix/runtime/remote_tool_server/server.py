"""gRPC server for remote tool execution."""

import json
import logging
import os
import signal
import sys
from concurrent import futures
from pathlib import Path
from typing import Any

import grpc

# Try to import generated gRPC code
try:
    from .proto import tool_service_pb2
    from .proto import tool_service_pb2_grpc

    PROTO_AVAILABLE = True
except ImportError:
    # Proto files not generated yet - will fail gracefully
    PROTO_AVAILABLE = False
    tool_service_pb2 = None  # type: ignore
    tool_service_pb2_grpc = None  # type: ignore

logger = logging.getLogger(__name__)

# Server configuration
SERVER_PORT = int(os.getenv("STRIX_SERVER_PORT", "50051"))
AUTH_TOKEN = os.getenv("STRIX_SERVER_TOKEN", "")
TOOL_POOL_SIZE = int(os.getenv("STRIX_TOOL_POOL_SIZE", "10"))

# Registered agents
_registered_agents: set[str] = set()

# Tool executor instance
_tool_executor: Any = None


def get_tool_executor() -> Any:
    """Get or create tool executor instance."""
    global _tool_executor
    if _tool_executor is None:
        from .tool_executor import ToolExecutor

        _tool_executor = ToolExecutor(pool_size=TOOL_POOL_SIZE)
    return _tool_executor


def verify_token(token: str) -> None:
    """Verify authentication token."""
    if not AUTH_TOKEN:
        raise ValueError("Server token not configured")
    if token != AUTH_TOKEN:
        raise ValueError("Invalid authentication token")


# gRPC service implementation
class ToolServiceServicer:
    """gRPC service implementation for tool execution."""

    def ExecuteTool(self, request: Any, context: Any) -> Any:
        """Execute a single tool."""
        if not PROTO_AVAILABLE:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Proto files not generated. Run generate_proto.py first.")
            return None

        try:
            verify_token(request.auth_token)

            # Parse kwargs from JSON strings
            kwargs = {}
            for key, value in request.kwargs.items():
                try:
                    kwargs[key] = json.loads(value)
                except json.JSONDecodeError:
                    kwargs[key] = value

            executor = get_tool_executor()
            result = executor.execute_tool(request.tool_name, kwargs)

            # Create response using generated proto
            response = tool_service_pb2.ToolResponse()
            if "error" in result:
                response.success = False
                response.error = result["error"]
                response.result = ""
                response.exit_code = 1
            else:
                response.success = True
                # Serialize result to JSON
                try:
                    response.result = json.dumps(result.get("result", ""))
                except (TypeError, ValueError):
                    response.result = str(result.get("result", ""))
                response.error = ""
                response.exit_code = 0

            return response

        except Exception as e:
            logger.exception(f"Error executing tool: {e}")
            response = tool_service_pb2.ToolResponse()
            response.success = False
            response.error = str(e)
            response.result = ""
            response.exit_code = 1
            return response

    def ExecuteBatch(self, request: Any, context: Any) -> Any:
        """Execute multiple tools in batch."""
        if not PROTO_AVAILABLE:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Proto files not generated. Run generate_proto.py first.")
            return None

        try:
            verify_token(request.auth_token)

            executor = get_tool_executor()

            # Parse tool specifications
            tools = []
            for tool_spec in request.tools:
                kwargs = {}
                for key, value in tool_spec.kwargs.items():
                    try:
                        kwargs[key] = json.loads(value)
                    except json.JSONDecodeError:
                        kwargs[key] = value

                tools.append({"tool_name": tool_spec.tool_name, "kwargs": kwargs})

            results = executor.execute_batch(tools)

            # Create batch response using generated proto
            batch_response = tool_service_pb2.BatchToolResponse()

            for result in results:
                tool_response = tool_service_pb2.ToolResponse()
                if "error" in result:
                    tool_response.success = False
                    tool_response.error = result["error"]
                    tool_response.result = ""
                    tool_response.exit_code = 1
                else:
                    tool_response.success = True
                    try:
                        tool_response.result = json.dumps(result.get("result", ""))
                    except (TypeError, ValueError):
                        tool_response.result = str(result.get("result", ""))
                    tool_response.error = ""
                    tool_response.exit_code = 0
                batch_response.results.append(tool_response)

            return batch_response

        except Exception as e:
            logger.exception(f"Error executing batch: {e}")
            batch_response = tool_service_pb2.BatchToolResponse()
            tool_response = tool_service_pb2.ToolResponse()
            tool_response.success = False
            tool_response.error = str(e)
            tool_response.result = ""
            tool_response.exit_code = 1
            batch_response.results.append(tool_response)
            return batch_response

    def HealthCheck(self, request: Any, context: Any) -> Any:
        """Health check endpoint."""
        if not PROTO_AVAILABLE:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Proto files not generated.")
            return None

        from strix.tools.registry import get_tool_names

        health_response = tool_service_pb2.HealthResponse()
        health_response.healthy = True
        health_response.version = "1.0.0"
        health_response.registered_agents = len(_registered_agents)
        health_response.tool_count = len(get_tool_names())

        # Check network connectivity
        try:
            import socket

            socket.gethostbyname("google.com")
            health_response.network_status = "connected"
        except Exception:
            health_response.network_status = "disconnected"

        return health_response

    def RegisterAgent(self, request: Any, context: Any) -> Any:
        """Register an agent with the server."""
        if not PROTO_AVAILABLE:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Proto files not generated.")
            return None

        try:
            verify_token(request.auth_token)
            _registered_agents.add(request.agent_id)

            response = tool_service_pb2.RegisterAgentResponse()
            response.success = True
            response.agent_id = request.agent_id
            response.message = f"Agent {request.agent_id} registered successfully"

            return response

        except Exception as e:
            logger.exception(f"Error registering agent: {e}")
            response = tool_service_pb2.RegisterAgentResponse()
            response.success = False
            response.agent_id = request.agent_id or "unknown"
            response.message = str(e)
            return response

    def StreamToolOutput(self, request: Any, context: Any) -> Any:
        """Stream tool output for long-running operations."""
        if not PROTO_AVAILABLE:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("Proto files not generated.")
            return

        try:
            verify_token(request.auth_token)

            # Parse kwargs from JSON strings
            kwargs = {}
            for key, value in request.kwargs.items():
                try:
                    kwargs[key] = json.loads(value)
                except json.JSONDecodeError:
                    kwargs[key] = value

            executor = get_tool_executor()
            
            # For now, execute the tool and yield results as chunks
            # This is a simple implementation - can be enhanced for true streaming
            result = executor.execute_tool(request.tool_name, kwargs)
            
            if "error" in result:
                response = tool_service_pb2.StreamResponse()
                response.done = True
                response.error = result["error"]
                response.chunk = ""
                yield response
            else:
                # Serialize result and send as single chunk
                try:
                    result_str = json.dumps(result.get("result", ""))
                except (TypeError, ValueError):
                    result_str = str(result.get("result", ""))
                
                response = tool_service_pb2.StreamResponse()
                response.chunk = result_str
                response.done = True
                response.error = ""
                yield response

        except Exception as e:
            logger.exception(f"Error in stream: {e}")
            response = tool_service_pb2.StreamResponse()
            response.done = True
            response.error = str(e)
            response.chunk = ""
            yield response


def serve() -> None:
    """Start the gRPC server."""
    if not AUTH_TOKEN:
        logger.error("STRIX_SERVER_TOKEN not set. Server cannot start without authentication.")
        sys.exit(1)

    if not PROTO_AVAILABLE:
        logger.error("Proto files not generated. Please run:")
        logger.error("  python -m strix.runtime.remote_tool_server.generate_proto")
        sys.exit(1)

    # Initialize tools before starting server
    logger.info("Initializing tools...")
    try:
        # Import tools to ensure they're registered
        import strix.tools  # noqa: F401
        from strix.tools.registry import get_tool_names
        
        tool_count = len(get_tool_names())
        logger.info(f"Initialized {tool_count} tools")
    except Exception as e:
        logger.warning(f"Tool initialization warning: {e}")
        # Continue anyway - tools will be loaded on demand

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=TOOL_POOL_SIZE))
    
    # Add service to server
    tool_service_pb2_grpc.add_ToolServiceServicer_to_server(
        ToolServiceServicer(), server
    )

    # Bind to port
    try:
        server.add_insecure_port(f"[::]:{SERVER_PORT}")
    except Exception as e:
        logger.error(f"Failed to bind to port {SERVER_PORT}: {e}")
        sys.exit(1)
    
    logger.info(f"Starting Strix Remote Tool Server on port {SERVER_PORT}")
    logger.info(f"Tool pool size: {TOOL_POOL_SIZE}")
    logger.info(f"Authentication: {'Enabled' if AUTH_TOKEN else 'Disabled'}")

    try:
        server.start()
        logger.info("Server started successfully")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

    def signal_handler(sig: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("Shutting down server...")
        executor = get_tool_executor()
        if executor:
            executor.shutdown()
        server.stop(grace=5)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        serve()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error starting server: {e}")
        sys.exit(1)
