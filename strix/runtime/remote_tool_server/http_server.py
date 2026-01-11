"""HTTP server for remote tool execution (Cloudflared-compatible).

This replaces the gRPC server with a simple HTTP/REST API that works better
with Cloudflared tunnels. Cloudflared Quick Tunnels don't properly handle
gRPC/HTTP2 frames, causing 403 errors.

REST API Endpoints:
- POST /execute - Execute a single tool
- POST /execute_batch - Execute multiple tools
- GET /health - Health check
- POST /register_agent - Register an agent
"""

import json
import logging
import os
import signal
import sys
from typing import Any

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

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


def get_metrics() -> Any:
    """Get metrics instance."""
    from .metrics import get_metrics as get_metrics_instance
    return get_metrics_instance()


def verify_token(token: str) -> bool:
    """Verify authentication token."""
    if not AUTH_TOKEN:
        logger.warning("Server token not configured - authentication disabled")
        return True
    return token == AUTH_TOKEN


class ToolServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for tool server."""
    
    def log_message(self, format: str, *args: Any) -> None:
        """Override to use Python logging."""
        logger.info("%s - %s" % (self.address_string(), format % args))
    
    def _send_json_response(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
    
    def _get_request_body(self) -> dict[str, Any]:
        """Parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))
    
    def _check_auth(self, request_data: dict[str, Any]) -> bool:
        """Check authentication from request."""
        # Check Authorization header first
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if verify_token(token):
                return True
        
        # Fallback to auth_token in body
        token = request_data.get("auth_token", "")
        return verify_token(token)
    
    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == "/health":
            self._handle_health()
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)
        
        try:
            request_data = self._get_request_body()
        except json.JSONDecodeError as e:
            self._send_json_response({"error": f"Invalid JSON: {e}"}, 400)
            return
        
        if parsed.path == "/execute":
            self._handle_execute(request_data)
        elif parsed.path == "/execute_batch":
            self._handle_execute_batch(request_data)
        elif parsed.path == "/register_agent":
            self._handle_register_agent(request_data)
        elif parsed.path == "/health":
            self._handle_health()
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def _handle_execute(self, request_data: dict[str, Any]) -> None:
        """Execute a single tool."""
        if not self._check_auth(request_data):
            self._send_json_response({"error": "Unauthorized"}, 401)
            return
        
        tool_name = request_data.get("tool_name", "")
        kwargs = request_data.get("kwargs", {})
        agent_id = request_data.get("agent_id", "unknown")
        
        if not tool_name:
            self._send_json_response({"error": "tool_name is required"}, 400)
            return
        
        try:
            import time
            exec_start = time.time()
            
            executor = get_tool_executor()
            result = executor.execute_tool(tool_name, kwargs)
            
            exec_duration = time.time() - exec_start
            metrics = get_metrics()
            metrics.record_tool_execution(tool_name, exec_duration, "error" not in result)
            
            if "error" in result:
                self._send_json_response({
                    "success": False,
                    "error": result["error"],
                    "result": None,
                    "exit_code": 1
                })
            else:
                self._send_json_response({
                    "success": True,
                    "result": result.get("result"),
                    "error": "",
                    "exit_code": 0
                })
        
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}: {e}")
            self._send_json_response({
                "success": False,
                "error": str(e),
                "result": None,
                "exit_code": 1
            })
    
    def _handle_execute_batch(self, request_data: dict[str, Any]) -> None:
        """Execute multiple tools in batch."""
        if not self._check_auth(request_data):
            self._send_json_response({"error": "Unauthorized"}, 401)
            return
        
        tools = request_data.get("tools", [])
        agent_id = request_data.get("agent_id", "unknown")
        
        if not tools:
            self._send_json_response({"error": "tools list is required"}, 400)
            return
        
        try:
            executor = get_tool_executor()
            
            # Convert tool specs format if needed
            tool_specs = []
            for tool in tools:
                tool_specs.append({
                    "tool_name": tool.get("tool_name", ""),
                    "kwargs": tool.get("kwargs", {})
                })
            
            results = executor.execute_batch(tool_specs)
            
            # Format results
            formatted_results = []
            for result in results:
                if "error" in result:
                    formatted_results.append({
                        "success": False,
                        "error": result["error"],
                        "result": None,
                        "exit_code": 1
                    })
                else:
                    formatted_results.append({
                        "success": True,
                        "result": result.get("result"),
                        "error": "",
                        "exit_code": 0
                    })
            
            self._send_json_response({"results": formatted_results})
        
        except Exception as e:
            logger.exception(f"Error executing batch: {e}")
            self._send_json_response({
                "error": str(e),
                "results": []
            })
    
    def _handle_register_agent(self, request_data: dict[str, Any]) -> None:
        """Register an agent with the server."""
        if not self._check_auth(request_data):
            self._send_json_response({"error": "Unauthorized"}, 401)
            return
        
        agent_id = request_data.get("agent_id", "")
        
        if not agent_id:
            self._send_json_response({
                "success": False,
                "agent_id": "",
                "message": "agent_id is required"
            }, 400)
            return
        
        _registered_agents.add(agent_id)
        
        self._send_json_response({
            "success": True,
            "agent_id": agent_id,
            "message": f"Agent {agent_id} registered successfully"
        })
    
    def _handle_health(self) -> None:
        """Health check endpoint."""
        try:
            from strix.tools.registry import get_tool_names
            from .connection_pool import get_connection_pool
            
            metrics = get_metrics()
            server_stats = metrics.get_server_stats()
            pool_stats = get_connection_pool().get_stats()
            
            # Check network connectivity
            network_status = "disconnected"
            try:
                import socket
                socket.gethostbyname("google.com")
                network_status = "connected"
            except Exception:
                pass
            
            health_data = {
                "healthy": True,
                "version": "1.0.0",
                "registered_agents": len(_registered_agents),
                "tool_count": len(get_tool_names()),
                "network_status": network_status,
                "metrics": {
                    "uptime_seconds": server_stats.get("uptime_seconds", 0),
                    "request_rate": server_stats.get("request_rate_per_minute", 0),
                    "error_rate": server_stats.get("error_rate", 0),
                    "total_requests": server_stats.get("total_requests", 0),
                },
                "connection_pool": pool_stats,
            }
            
            self._send_json_response(health_data)
        
        except Exception as e:
            logger.exception(f"Health check error: {e}")
            self._send_json_response({
                "healthy": False,
                "error": str(e)
            })


class ThreadedHTTPServer(HTTPServer):
    """Handle requests in separate threads."""
    allow_reuse_address = True
    
    def process_request(self, request: Any, client_address: Any) -> None:
        """Process request in a new thread."""
        thread = threading.Thread(
            target=self.process_request_thread,
            args=(request, client_address)
        )
        thread.daemon = True
        thread.start()
    
    def process_request_thread(self, request: Any, client_address: Any) -> None:
        """Process request in thread."""
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def serve() -> None:
    """Start the HTTP server."""
    if not AUTH_TOKEN:
        logger.warning("STRIX_SERVER_TOKEN not set. Server will run without authentication!")
    
    # Initialize tools before starting server
    logger.info("Initializing tools...")
    try:
        import strix.tools  # noqa: F401
        from strix.tools.registry import get_tool_names
        
        tool_count = len(get_tool_names())
        logger.info(f"Initialized {tool_count} tools")
    except Exception as e:
        logger.warning(f"Tool initialization warning: {e}")
    
    # Create HTTP server
    server_address = ("0.0.0.0", SERVER_PORT)
    httpd = ThreadedHTTPServer(server_address, ToolServerHandler)
    
    logger.info(f"Starting Strix HTTP Tool Server on port {SERVER_PORT}")
    logger.info(f"Tool pool size: {TOOL_POOL_SIZE}")
    logger.info(f"Authentication: {'Enabled' if AUTH_TOKEN else 'Disabled (WARNING!)'}")
    logger.info(f"Endpoints available:")
    logger.info(f"  - GET  /health          - Health check")
    logger.info(f"  - POST /execute         - Execute single tool")
    logger.info(f"  - POST /execute_batch   - Execute batch of tools")
    logger.info(f"  - POST /register_agent  - Register agent")
    
    def signal_handler(sig: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info("Shutting down server...")
        executor = get_tool_executor()
        if executor:
            executor.shutdown()
        httpd.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        logger.info("Server started successfully - ready to accept connections")
        httpd.serve_forever()
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
