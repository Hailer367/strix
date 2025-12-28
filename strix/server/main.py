"""
Strix Web Server - FastAPI application for hosted mode
Provides REST API and WebSocket endpoints for the web dashboard
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Strix Security Dashboard API",
    description="REST API and WebSocket server for Strix AI Security Testing",
    version="0.5.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class ServerState:
    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}
        self.active_scans: dict[str, dict[str, Any]] = {}
        self.scan_history: list[dict[str, Any]] = []
        self.agents: dict[str, dict[str, Any]] = {}
        self.messages: list[dict[str, Any]] = []
        self.tool_executions: dict[str, dict[str, Any]] = {}
        self.vulnerabilities: list[dict[str, Any]] = []
        self.scan_tasks: dict[str, asyncio.Task[Any]] = {}

state = ServerState()


# Pydantic models
class TargetConfig(BaseModel):
    type: str = Field(..., description="Target type: web_application, repository, local_code, ip_address")
    value: str = Field(..., description="Target value (URL, path, IP)")


class ScanConfig(BaseModel):
    name: Optional[str] = Field(None, description="Scan name")
    targets: list[TargetConfig] = Field(..., description="List of targets to scan")
    mode: str = Field("deep", description="Scan mode: quick, standard, deep")
    instructions: Optional[str] = Field(None, description="Custom instructions for the scan")


class SettingsConfig(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    max_iterations: Optional[int] = None
    # CLIProxyAPI settings
    cliproxy_enabled: Optional[bool] = None
    cliproxy_base_url: Optional[str] = None
    cliproxy_management_key: Optional[str] = None


class UserMessage(BaseModel):
    agent_id: str
    content: str


# WebSocket connection manager
class ConnectionManager:
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        state.connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str) -> None:
        if client_id in state.connections:
            del state.connections[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send message to all connected clients"""
        disconnected = []
        for client_id, websocket in state.connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> None:
        """Send message to specific client"""
        if client_id in state.connections:
            try:
                await state.connections[client_id].send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")


manager = ConnectionManager()


# Event emitters (to be called by Strix agent integration)
async def emit_agent_created(agent_data: dict[str, Any]) -> None:
    """Emit when a new agent is created"""
    state.agents[agent_data["id"]] = agent_data
    await manager.broadcast({
        "type": "agent_created",
        "payload": agent_data,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def emit_agent_updated(agent_id: str, updates: dict[str, Any]) -> None:
    """Emit when an agent is updated"""
    if agent_id in state.agents:
        state.agents[agent_id].update(updates)
    await manager.broadcast({
        "type": "agent_updated",
        "payload": {"id": agent_id, "updates": updates},
        "timestamp": datetime.utcnow().isoformat(),
    })


async def emit_chat_message(agent_id: str, role: str, content: str) -> None:
    """Emit a new chat message"""
    message = {
        "id": str(uuid.uuid4()),
        "agentId": agent_id,
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    state.messages.append(message)
    await manager.broadcast({
        "type": "chat_message",
        "payload": message,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def emit_tool_execution(
    agent_id: str,
    tool_name: str,
    args: dict[str, Any],
    status: str = "running",
    result: Any = None,
) -> str:
    """Emit a tool execution event"""
    exec_id = str(uuid.uuid4())
    execution = {
        "id": exec_id,
        "agentId": agent_id,
        "toolName": tool_name,
        "args": args,
        "status": status,
        "result": result,
        "timestamp": datetime.utcnow().isoformat(),
    }
    state.tool_executions[exec_id] = execution
    await manager.broadcast({
        "type": "tool_execution",
        "payload": execution,
        "timestamp": datetime.utcnow().isoformat(),
    })
    return exec_id


async def emit_tool_update(exec_id: str, status: str, result: Any = None) -> None:
    """Update a tool execution status"""
    if exec_id in state.tool_executions:
        state.tool_executions[exec_id]["status"] = status
        if result is not None:
            state.tool_executions[exec_id]["result"] = result
    await manager.broadcast({
        "type": "tool_update",
        "payload": {"id": exec_id, "updates": {"status": status, "result": result}},
        "timestamp": datetime.utcnow().isoformat(),
    })


async def emit_vulnerability(vuln_data: dict[str, Any]) -> None:
    """Emit when a vulnerability is found"""
    vuln = {
        "id": str(uuid.uuid4()),
        **vuln_data,
        "timestamp": datetime.utcnow().isoformat(),
    }
    state.vulnerabilities.append(vuln)
    await manager.broadcast({
        "type": "vulnerability_found",
        "payload": vuln,
        "timestamp": datetime.utcnow().isoformat(),
    })


async def emit_scan_status(scan_id: str, status: str, stats: Optional[dict[str, Any]] = None) -> None:
    """Emit scan status update"""
    if scan_id in state.active_scans:
        state.active_scans[scan_id]["status"] = status
        if stats:
            state.active_scans[scan_id]["stats"] = stats
    await manager.broadcast({
        "type": "scan_status",
        "payload": {"scanId": scan_id, "status": status, "stats": stats},
        "timestamp": datetime.utcnow().isoformat(),
    })


# REST API endpoints
@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Strix Security Dashboard API", "version": "0.5.0"}


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "connections": len(state.connections),
        "active_scans": len(state.active_scans),
        "agents": len(state.agents),
    }


@app.post("/api/scan/start")
async def start_scan(config: ScanConfig) -> dict[str, Any]:
    """Start a new security scan"""
    scan_id = str(uuid.uuid4())
    scan_name = config.name or f"Scan {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    scan_data = {
        "id": scan_id,
        "name": scan_name,
        "targets": [t.model_dump() for t in config.targets],
        "mode": config.mode,
        "instructions": config.instructions,
        "status": "running",
        "createdAt": datetime.utcnow().isoformat(),
        "completedAt": None,
        "stats": {
            "totalAgents": 0,
            "activeAgents": 0,
            "completedAgents": 0,
            "vulnerabilitiesFound": 0,
            "iterationsUsed": 0,
            "duration": 0,
        },
    }

    state.active_scans[scan_id] = scan_data
    state.scan_history.append(scan_data)

    # Start the scan in background
    task = asyncio.create_task(run_strix_scan(scan_id, config))
    state.scan_tasks[scan_id] = task

    await manager.broadcast({
        "type": "scan_status",
        "payload": scan_data,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return scan_data


@app.post("/api/scan/{scan_id}/stop")
async def stop_scan(scan_id: str) -> dict[str, Any]:
    """Stop a running scan"""
    if scan_id not in state.active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan_id in state.scan_tasks:
        state.scan_tasks[scan_id].cancel()
        del state.scan_tasks[scan_id]

    state.active_scans[scan_id]["status"] = "stopped"
    state.active_scans[scan_id]["completedAt"] = datetime.utcnow().isoformat()

    await emit_scan_status(scan_id, "stopped")

    return {"message": "Scan stopped", "scanId": scan_id}


@app.get("/api/scan/{scan_id}")
async def get_scan(scan_id: str) -> dict[str, Any]:
    """Get scan details"""
    if scan_id not in state.active_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return state.active_scans[scan_id]


@app.get("/api/scans")
async def list_scans() -> list[dict[str, Any]]:
    """List all scans"""
    return state.scan_history


@app.get("/api/agents")
async def list_agents() -> dict[str, dict[str, Any]]:
    """List all agents"""
    return state.agents


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    """Get agent details"""
    if agent_id not in state.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return state.agents[agent_id]


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str) -> dict[str, Any]:
    """Stop a specific agent"""
    if agent_id not in state.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Signal agent to stop via the agents graph
    try:
        from strix.tools.agents_graph.agents_graph_actions import stop_agent as strix_stop_agent
        result = strix_stop_agent(agent_id)
        return result
    except ImportError:
        return {"success": False, "error": "Agent control not available"}


@app.post("/api/agents/{agent_id}/message")
async def send_message(agent_id: str, message: UserMessage) -> dict[str, Any]:
    """Send a message to an agent"""
    if agent_id not in state.agents:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        from strix.tools.agents_graph.agents_graph_actions import send_user_message_to_agent
        send_user_message_to_agent(agent_id, message.content)
        await emit_chat_message(agent_id, "user", message.content)
        return {"success": True, "message": "Message sent"}
    except ImportError:
        return {"success": False, "error": "Agent messaging not available"}


@app.get("/api/vulnerabilities")
async def list_vulnerabilities() -> list[dict[str, Any]]:
    """List all vulnerabilities"""
    return state.vulnerabilities


@app.get("/api/messages")
async def list_messages(agent_id: Optional[str] = None) -> list[dict[str, Any]]:
    """List messages, optionally filtered by agent"""
    if agent_id:
        return [m for m in state.messages if m.get("agentId") == agent_id]
    return state.messages


@app.post("/api/settings")
async def update_settings(settings: SettingsConfig) -> dict[str, Any]:
    """Update server settings (environment variables)"""
    # CLIProxyAPI settings (takes precedence)
    if settings.cliproxy_enabled is not None:
        os.environ["CLIPROXY_ENABLED"] = str(settings.cliproxy_enabled).lower()
    if settings.cliproxy_base_url:
        os.environ["CLIPROXY_BASE_URL"] = settings.cliproxy_base_url
    if settings.cliproxy_management_key:
        os.environ["CLIPROXY_MANAGEMENT_KEY"] = settings.cliproxy_management_key
    
    # Standard LLM settings
    if settings.llm_provider and settings.llm_model:
        # For cliproxy, don't prefix with provider
        if settings.llm_provider == "cliproxy":
            os.environ["STRIX_LLM"] = settings.llm_model
            os.environ["CLIPROXY_ENABLED"] = "true"
            # Auto-set API base to CLIProxyAPI
            if not settings.api_base:
                cliproxy_url = settings.cliproxy_base_url or os.getenv("CLIPROXY_BASE_URL", "http://localhost:8317/v1")
                os.environ["LLM_API_BASE"] = cliproxy_url
        else:
            os.environ["STRIX_LLM"] = f"{settings.llm_provider}/{settings.llm_model}"
    
    if settings.api_key:
        os.environ["LLM_API_KEY"] = settings.api_key
    if settings.api_base:
        os.environ["LLM_API_BASE"] = settings.api_base
    if settings.perplexity_api_key:
        os.environ["PERPLEXITY_API_KEY"] = settings.perplexity_api_key

    return {"success": True, "message": "Settings updated"}


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    """Get current server settings"""
    return {
        "llm_model": os.getenv("STRIX_LLM", "gemini-2.5-pro"),
        "api_base": os.getenv("LLM_API_BASE", ""),
        "has_api_key": bool(os.getenv("LLM_API_KEY")),
        "has_perplexity_key": bool(os.getenv("PERPLEXITY_API_KEY")),
        "cliproxy_enabled": os.getenv("CLIPROXY_ENABLED", "true").lower() == "true",
        "cliproxy_base_url": os.getenv("CLIPROXY_BASE_URL", "http://localhost:8317/v1"),
    }


@app.get("/api/cliproxy/status")
async def cliproxy_status() -> dict[str, Any]:
    """Check CLIProxyAPI connection status"""
    import httpx
    
    cliproxy_url = os.getenv("CLIPROXY_BASE_URL", "http://localhost:8317")
    management_key = os.getenv("CLIPROXY_MANAGEMENT_KEY", "")
    
    try:
        headers = {}
        if management_key:
            headers["Authorization"] = f"Bearer {management_key}"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{cliproxy_url}/v0/management/config", headers=headers)
            
            if response.status_code == 200:
                config = response.json()
                return {
                    "connected": True,
                    "base_url": cliproxy_url,
                    "debug": config.get("debug", False),
                    "has_gemini": bool(config.get("gemini-api-key", [])),
                    "has_claude": bool(config.get("claude-api-key", [])),
                    "has_codex": bool(config.get("codex-api-key", [])),
                }
            else:
                return {
                    "connected": False,
                    "error": f"HTTP {response.status_code}",
                }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)

    # Send initial state
    await websocket.send_json({
        "type": "connection_status",
        "payload": {
            "connected": True,
            "clientId": client_id,
            "agents": state.agents,
            "messages": state.messages[-100:],  # Last 100 messages
            "vulnerabilities": state.vulnerabilities,
            "activeScan": next(
                (s for s in state.active_scans.values() if s["status"] == "running"),
                None
            ),
        },
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            data = await websocket.receive_json()
            await handle_websocket_message(client_id, data)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)


async def handle_websocket_message(client_id: str, data: dict[str, Any]) -> None:
    """Handle incoming WebSocket messages"""
    msg_type = data.get("type")
    payload = data.get("payload", {})

    if msg_type == "ping":
        await manager.send_to_client(client_id, {
            "type": "pong",
            "payload": {},
            "timestamp": datetime.utcnow().isoformat(),
        })

    elif msg_type == "scan_status":
        action = payload.get("action")
        if action == "start":
            config = ScanConfig(**payload.get("config", {}))
            await start_scan(config)
        elif action == "stop":
            scan_id = payload.get("scanId")
            if scan_id:
                await stop_scan(scan_id)

    elif msg_type == "chat_message":
        agent_id = payload.get("agentId")
        content = payload.get("content")
        if agent_id and content:
            message = UserMessage(agent_id=agent_id, content=content)
            await send_message(agent_id, message)

    elif msg_type == "agent_updated":
        agent_id = payload.get("id")
        action = payload.get("action")
        if agent_id and action == "stop":
            await stop_agent(agent_id)


# Strix integration
async def run_strix_scan(scan_id: str, config: ScanConfig) -> None:
    """Run Strix scan and emit events to connected clients"""
    try:
        from strix.agents.StrixAgent import StrixAgent
        from strix.llm.config import LLMConfig
        from strix.telemetry.tracer import Tracer, set_global_tracer

        # Create tracer with custom callbacks
        tracer = Tracer(scan_id)

        # Set up callbacks to emit events
        original_log_agent = tracer.log_agent_creation

        def log_agent_wrapper(
            agent_id: str,
            name: str,
            task: str,
            parent_id: Optional[str] = None,
        ) -> None:
            original_log_agent(agent_id, name, task, parent_id)
            asyncio.create_task(emit_agent_created({
                "id": agent_id,
                "name": name,
                "task": task,
                "parentId": parent_id,
                "status": "running",
                "createdAt": datetime.utcnow().isoformat(),
                "iteration": 0,
                "maxIterations": 300,
                "promptModules": [],
            }))

        tracer.log_agent_creation = log_agent_wrapper

        original_update_status = tracer.update_agent_status

        def update_status_wrapper(
            agent_id: str,
            status: str,
            error_message: Optional[str] = None,
        ) -> None:
            original_update_status(agent_id, status, error_message)
            asyncio.create_task(emit_agent_updated(agent_id, {
                "status": status,
                "errorMessage": error_message,
            }))

        tracer.update_agent_status = update_status_wrapper

        original_log_chat = tracer.log_chat_message

        def log_chat_wrapper(
            content: str,
            role: str,
            agent_id: str,
        ) -> None:
            original_log_chat(content, role, agent_id)
            asyncio.create_task(emit_chat_message(agent_id, role, content))

        tracer.log_chat_message = log_chat_wrapper

        # Vulnerability callback
        def vuln_callback(
            report_id: str,
            title: str,
            content: str,
            severity: str,
        ) -> None:
            asyncio.create_task(emit_vulnerability({
                "title": title,
                "severity": severity.lower(),
                "description": content,
                "poc": "",
                "impact": "",
                "remediation": "",
                "agentId": "",
                "target": config.targets[0].value if config.targets else "",
            }))

        tracer.vulnerability_found_callback = vuln_callback

        set_global_tracer(tracer)

        # Build scan config
        targets_info = []
        for target in config.targets:
            if target.type == "web_application":
                targets_info.append({
                    "type": "web_application",
                    "details": {"target_url": target.value},
                    "original": target.value,
                })
            elif target.type == "repository":
                targets_info.append({
                    "type": "repository",
                    "details": {"target_repo": target.value},
                    "original": target.value,
                })
            elif target.type == "local_code":
                targets_info.append({
                    "type": "local_code",
                    "details": {"target_path": target.value},
                    "original": target.value,
                })
            elif target.type == "ip_address":
                targets_info.append({
                    "type": "ip_address",
                    "details": {"target_ip": target.value},
                    "original": target.value,
                })

        scan_config = {
            "scan_id": scan_id,
            "targets": targets_info,
            "user_instructions": config.instructions or "",
            "run_name": scan_id,
        }

        tracer.set_scan_config(scan_config)

        # Create and run agent
        llm_config = LLMConfig(scan_mode=config.mode)
        agent_config = {
            "llm_config": llm_config,
            "max_iterations": 300,
            "non_interactive": True,
        }

        agent = StrixAgent(agent_config)
        await agent.execute_scan(scan_config)

        # Mark scan as completed
        state.active_scans[scan_id]["status"] = "completed"
        state.active_scans[scan_id]["completedAt"] = datetime.utcnow().isoformat()
        await emit_scan_status(scan_id, "completed")

    except asyncio.CancelledError:
        logger.info(f"Scan {scan_id} was cancelled")
        state.active_scans[scan_id]["status"] = "stopped"
        await emit_scan_status(scan_id, "stopped")
    except Exception as e:
        logger.error(f"Scan {scan_id} failed: {e}")
        state.active_scans[scan_id]["status"] = "failed"
        await emit_scan_status(scan_id, "failed")
        await manager.broadcast({
            "type": "error",
            "payload": {"message": str(e), "scanId": scan_id},
            "timestamp": datetime.utcnow().isoformat(),
        })


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the Strix web server"""
    import uvicorn
    logger.info(f"Starting Strix server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
