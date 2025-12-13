#!/usr/bin/env python3
"""
Strix Dashboard Server

A FastAPI-based web server that provides a configuration dashboard for
autonomous bug bounty operations through GitHub Actions.

Features:
- Configure-and-Fire: Set all parameters before starting
- Roo Code OAuth: Browser-based authentication
- Real-time WebSocket: Live updates on scan progress
- Extensible: Add custom configuration options
"""

import asyncio
import json
import logging
import os
import secrets
import signal
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import (
    DEFAULT_FOCUS_AREAS,
    ROOCODE_MODELS,
    AccessConfig,
    AIConfig,
    AIProvider,
    DashboardConfig,
    DashboardState,
    OutputConfig,
    ScanConfig,
    ScanStatus,
    TargetConfig,
    TestingConfig,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dashboard directory
DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"

# Global state
dashboard_config = DashboardConfig()
dashboard_state = DashboardState()
connected_websockets: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    logger.info("Strix Dashboard starting up...")
    yield
    logger.info("Strix Dashboard shutting down...")
    # Clean up connected websockets
    for ws in connected_websockets:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass


def create_app(config: DashboardConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global dashboard_config
    
    if config:
        dashboard_config = config
    
    app = FastAPI(
        title="Strix Autonomous Dashboard",
        description="Configuration dashboard for Strix autonomous bug bounty operations",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Mount static files if directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Setup templates
    templates = None
    if TEMPLATES_DIR.exists():
        templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    
    # =========================================================================
    # API Routes
    # =========================================================================
    
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request) -> HTMLResponse:
        """Serve the main dashboard page."""
        return HTMLResponse(content=get_dashboard_html(), status_code=200)
    
    @app.get("/api/status")
    async def get_status() -> dict[str, Any]:
        """Get current dashboard and scan status."""
        return {
            "status": dashboard_state.status.value,
            "progress": dashboard_state.progress,
            "current_action": dashboard_state.current_action,
            "findings_count": len(dashboard_state.findings),
            "connected_clients": len(connected_websockets),
            "start_time": dashboard_state.start_time.isoformat() if dashboard_state.start_time else None,
        }
    
    @app.get("/api/config")
    async def get_config() -> dict[str, Any]:
        """Get current scan configuration."""
        if dashboard_state.config:
            return dashboard_state.config.model_dump()
        return {"message": "No configuration set"}
    
    @app.post("/api/config")
    async def set_config(request: Request) -> dict[str, Any]:
        """Set scan configuration."""
        try:
            data = await request.json()
            
            # Build configuration from request data
            targets = TargetConfig(
                primary=data.get("target", ""),
                additional=data.get("additional_targets", []),
                exclusions=data.get("exclusions", []),
            )
            
            ai_provider = AIProvider(data.get("ai_provider", "roocode"))
            ai_config = AIConfig(
                provider=ai_provider,
                model=data.get("ai_model", "grok-code-fast-1"),
                api_key=data.get("api_key"),
                api_base=data.get("api_base"),
            )
            
            access_config = AccessConfig(
                level=data.get("access_level", "root"),
                allow_package_install=data.get("allow_package_install", True),
                allow_tool_download=data.get("allow_tool_download", True),
                allow_network_config=data.get("allow_network_config", True),
                allow_system_modification=data.get("allow_system_modification", True),
                command_timeout=data.get("command_timeout", 600),
            )
            
            testing_config = TestingConfig(
                instructions=data.get("instructions", ""),
                focus_areas=data.get("focus_areas", []),
                credentials=data.get("credentials", {}),
                max_iterations=data.get("max_iterations", 300),
                duration_minutes=data.get("duration_minutes", 60),
            )
            
            output_config = OutputConfig(
                format=data.get("output_format", "markdown"),
                severity_threshold=data.get("severity_threshold", "info"),
                notification_webhook=data.get("notification_webhook"),
                save_artifacts=data.get("save_artifacts", True),
            )
            
            scan_config = ScanConfig(
                ai=ai_config,
                access=access_config,
                targets=targets,
                testing=testing_config,
                output=output_config,
                run_id=os.getenv("STRIX_RUN_ID", secrets.token_hex(8)),
                created_at=datetime.now(UTC),
                status=ScanStatus.CONFIGURING,
            )
            
            dashboard_state.config = scan_config
            dashboard_state.status = ScanStatus.CONFIGURING
            
            # Save configuration to file
            config_path = Path(dashboard_config.config_file)
            config_path.write_text(scan_config.model_dump_json(indent=2))
            
            # Broadcast update to all connected clients
            await broadcast_update({
                "type": "config_updated",
                "config": scan_config.model_dump(),
            })
            
            return {
                "success": True,
                "message": "Configuration saved",
                "config": scan_config.model_dump(),
            }
            
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    @app.post("/api/start")
    async def start_scan() -> dict[str, Any]:
        """Start the autonomous scan with current configuration."""
        if not dashboard_state.config:
            raise HTTPException(status_code=400, detail="No configuration set")
        
        if dashboard_state.status == ScanStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Scan already running")
        
        try:
            # Update status
            dashboard_state.status = ScanStatus.RUNNING
            dashboard_state.config.status = ScanStatus.RUNNING
            dashboard_state.config.started_at = datetime.now(UTC)
            dashboard_state.start_time = datetime.now(UTC)
            dashboard_state.current_action = "Initializing scan..."
            
            # Create ready file to signal GitHub Actions
            ready_path = Path(dashboard_config.ready_file)
            ready_path.write_text(datetime.now(UTC).isoformat())
            
            # Broadcast update
            await broadcast_update({
                "type": "scan_started",
                "started_at": dashboard_state.start_time.isoformat(),
            })
            
            return {
                "success": True,
                "message": "Scan started - agent will now run autonomously",
                "run_id": dashboard_state.config.run_id,
            }
            
        except Exception as e:
            dashboard_state.status = ScanStatus.FAILED
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    @app.get("/api/findings")
    async def get_findings() -> dict[str, Any]:
        """Get current vulnerability findings."""
        return {
            "findings": dashboard_state.findings,
            "count": len(dashboard_state.findings),
        }
    
    @app.get("/api/logs")
    async def get_logs(limit: int = 100) -> dict[str, Any]:
        """Get recent log entries."""
        return {
            "logs": dashboard_state.logs[-limit:],
            "total": len(dashboard_state.logs),
        }
    
    @app.get("/api/models")
    async def get_models() -> dict[str, Any]:
        """Get available AI models."""
        return {
            "roocode": ROOCODE_MODELS,
            "focus_areas": DEFAULT_FOCUS_AREAS,
        }
    
    @app.post("/api/roocode/auth")
    async def roocode_auth(request: Request) -> dict[str, Any]:
        """Initiate Roo Code authentication."""
        try:
            from strix.llm.roocode_provider import get_roocode_provider
            
            provider = get_roocode_provider()
            
            if provider.is_authenticated():
                user_info = provider.get_user_info()
                return {
                    "success": True,
                    "authenticated": True,
                    "user": user_info,
                }
            
            # For CI/CD, use token from environment
            token = os.getenv("ROOCODE_ACCESS_TOKEN")
            if token:
                from strix.llm.roocode_provider import RooCodeCredentials
                provider.credentials = RooCodeCredentials(access_token=token)
                provider._save_credentials()
                return {
                    "success": True,
                    "authenticated": True,
                    "message": "Authenticated with environment token",
                }
            
            return {
                "success": False,
                "authenticated": False,
                "message": "Please set ROOCODE_ACCESS_TOKEN environment variable",
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        connected_websockets.append(websocket)
        
        try:
            # Send initial state
            await websocket.send_json({
                "type": "connected",
                "status": dashboard_state.status.value,
                "config": dashboard_state.config.model_dump() if dashboard_state.config else None,
            })
            
            while True:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            connected_websockets.remove(websocket)
        except Exception:  # noqa: BLE001
            if websocket in connected_websockets:
                connected_websockets.remove(websocket)
    
    return app


async def broadcast_update(data: dict[str, Any]) -> None:
    """Broadcast update to all connected WebSocket clients."""
    for ws in connected_websockets[:]:  # Copy list to avoid modification during iteration
        try:
            await ws.send_json(data)
        except Exception:  # noqa: BLE001
            connected_websockets.remove(ws)


def add_finding(finding: dict[str, Any]) -> None:
    """Add a vulnerability finding."""
    dashboard_state.findings.append(finding)
    # Trigger async broadcast
    asyncio.create_task(broadcast_update({
        "type": "finding",
        "finding": finding,
    }))


def add_log(message: str) -> None:
    """Add a log entry."""
    timestamp = datetime.now(UTC).isoformat()
    log_entry = f"[{timestamp}] {message}"
    dashboard_state.logs.append(log_entry)
    # Keep only last 1000 logs
    if len(dashboard_state.logs) > 1000:
        dashboard_state.logs = dashboard_state.logs[-1000:]


def update_progress(progress: int, action: str) -> None:
    """Update scan progress."""
    dashboard_state.progress = progress
    dashboard_state.current_action = action
    asyncio.create_task(broadcast_update({
        "type": "progress",
        "progress": progress,
        "action": action,
    }))


def get_dashboard_html() -> str:
    """Generate the dashboard HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strix Autonomous Dashboard</title>
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-primary: #22c55e;
            --accent-secondary: #3b82f6;
            --accent-warning: #f59e0b;
            --accent-danger: #ef4444;
            --border-color: #475569;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .logo-icon {
            font-size: 2.5rem;
        }
        
        .logo-text h1 {
            font-size: 1.5rem;
            color: var(--accent-primary);
        }
        
        .logo-text p {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .status-pending { background: var(--bg-tertiary); }
        .status-configuring { background: var(--accent-secondary); }
        .status-running { background: var(--accent-primary); color: #000; }
        .status-completed { background: var(--accent-primary); color: #000; }
        .status-failed { background: var(--accent-danger); }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-top: 2rem;
        }
        
        .card {
            background: var(--bg-secondary);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }
        
        .card-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-header h2 {
            font-size: 1.125rem;
            font-weight: 600;
        }
        
        .card-body {
            padding: 1.5rem;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 0.75rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            color: var(--text-primary);
            font-size: 1rem;
        }
        
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: var(--accent-primary);
        }
        
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: auto;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
        }
        
        .btn-primary {
            background: var(--accent-primary);
            color: #000;
        }
        
        .btn-primary:hover {
            background: #16a34a;
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }
        
        .btn-danger {
            background: var(--accent-danger);
            color: #fff;
        }
        
        .btn-large {
            padding: 1rem 2rem;
            font-size: 1.125rem;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .fire-btn {
            width: 100%;
            margin-top: 1rem;
            background: linear-gradient(135deg, var(--accent-danger), var(--accent-warning));
        }
        
        .fire-btn:hover {
            transform: scale(1.02);
        }
        
        .model-cards {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        
        .model-card {
            padding: 1rem;
            background: var(--bg-tertiary);
            border-radius: 0.5rem;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
        }
        
        .model-card:hover {
            border-color: var(--accent-secondary);
        }
        
        .model-card.selected {
            border-color: var(--accent-primary);
            background: rgba(34, 197, 94, 0.1);
        }
        
        .model-card h3 {
            font-size: 0.875rem;
            margin-bottom: 0.25rem;
        }
        
        .model-card p {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .focus-areas {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .focus-tag {
            padding: 0.375rem 0.75rem;
            background: var(--bg-tertiary);
            border-radius: 9999px;
            font-size: 0.75rem;
            cursor: pointer;
            border: 1px solid var(--border-color);
            transition: all 0.2s;
        }
        
        .focus-tag:hover {
            border-color: var(--accent-secondary);
        }
        
        .focus-tag.selected {
            background: var(--accent-secondary);
            border-color: var(--accent-secondary);
        }
        
        .findings-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .finding-item {
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        
        .finding-item:last-child {
            border-bottom: none;
        }
        
        .finding-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .finding-title {
            font-weight: 500;
        }
        
        .severity-badge {
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .severity-critical { background: #dc2626; }
        .severity-high { background: #ea580c; }
        .severity-medium { background: #d97706; }
        .severity-low { background: #2563eb; }
        .severity-info { background: #6b7280; }
        
        .progress-bar {
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 9999px;
            overflow: hidden;
            margin-bottom: 1rem;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            transition: width 0.3s;
        }
        
        .logs-container {
            background: var(--bg-primary);
            border-radius: 0.5rem;
            padding: 1rem;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.875rem;
        }
        
        .log-entry {
            padding: 0.25rem 0;
            color: var(--text-secondary);
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        .warning-notice {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 1rem;
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid var(--accent-warning);
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
        }
        
        .warning-notice p {
            font-size: 0.875rem;
            color: var(--accent-warning);
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <span class="logo-icon">&#129417;</span>
            <div class="logo-text">
                <h1>Strix Autonomous Dashboard</h1>
                <p>Configure and Fire - Bug Bounty Automation</p>
            </div>
        </div>
        <div id="statusBadge" class="status-badge status-pending">
            <span id="statusDot">&#9679;</span>
            <span id="statusText">Pending Configuration</span>
        </div>
    </header>
    
    <div class="container">
        <div class="main-content">
            <!-- Configuration Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#9881; Configuration</h2>
                </div>
                <div class="card-body">
                    <div class="warning-notice">
                        <span>&#9888;</span>
                        <p><strong>Configure and Fire:</strong> Once started, the agent runs autonomously without interruption. Configure everything before launching.</p>
                    </div>
                    
                    <div class="form-group">
                        <label>Primary Target *</label>
                        <input type="text" id="target" placeholder="https://example.com or https://github.com/org/repo" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Additional Targets (one per line)</label>
                        <textarea id="additionalTargets" placeholder="https://api.example.com&#10;https://staging.example.com"></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label>Duration (minutes)</label>
                        <input type="number" id="duration" value="60" min="5" max="480">
                    </div>
                    
                    <div class="form-group">
                        <label>Custom Instructions</label>
                        <textarea id="instructions" placeholder="Focus on authentication vulnerabilities. Test account: user@test.com / password123"></textarea>
                    </div>
                </div>
            </div>
            
            <!-- AI Provider Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#129302; AI Provider</h2>
                    <button class="btn btn-secondary" id="authBtn">Authenticate</button>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="aiProvider">
                            <option value="roocode" selected>Roo Code Cloud (Free)</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Model</label>
                        <div class="model-cards">
                            <div class="model-card selected" data-model="grok-code-fast-1">
                                <h3>Grok Code Fast 1</h3>
                                <p>Fast - 262K context</p>
                            </div>
                            <div class="model-card" data-model="roo/code-supernova">
                                <h3>Code Supernova</h3>
                                <p>Advanced - 200K context</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="form-group" id="apiKeyGroup" style="display: none;">
                        <label>API Key</label>
                        <input type="password" id="apiKey" placeholder="sk-...">
                    </div>
                </div>
            </div>
            
            <!-- Access Control Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#128274; Access Control</h2>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label>Access Level</label>
                        <select id="accessLevel">
                            <option value="root" selected>Root (Full Access)</option>
                            <option value="elevated">Elevated (Sudo Available)</option>
                            <option value="standard">Standard (Limited)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="allowPackageInstall" checked>
                            <label for="allowPackageInstall">Allow package installation</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="allowToolDownload" checked>
                            <label for="allowToolDownload">Allow tool downloads</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="allowNetworkConfig" checked>
                            <label for="allowNetworkConfig">Allow network configuration</label>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Command Timeout (seconds)</label>
                        <input type="number" id="commandTimeout" value="600" min="60" max="3600">
                    </div>
                </div>
            </div>
            
            <!-- Focus Areas Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#127919; Focus Areas</h2>
                </div>
                <div class="card-body">
                    <p style="margin-bottom: 1rem; color: var(--text-secondary); font-size: 0.875rem;">
                        Select vulnerability types to prioritize (leave empty for comprehensive testing)
                    </p>
                    <div class="focus-areas" id="focusAreas">
                        <span class="focus-tag" data-focus="sqli">SQL Injection</span>
                        <span class="focus-tag" data-focus="xss">XSS</span>
                        <span class="focus-tag" data-focus="ssrf">SSRF</span>
                        <span class="focus-tag" data-focus="idor">IDOR</span>
                        <span class="focus-tag" data-focus="auth_bypass">Auth Bypass</span>
                        <span class="focus-tag" data-focus="rce">RCE</span>
                        <span class="focus-tag" data-focus="lfi">LFI/RFI</span>
                        <span class="focus-tag" data-focus="csrf">CSRF</span>
                        <span class="focus-tag" data-focus="ssti">SSTI</span>
                        <span class="focus-tag" data-focus="xxe">XXE</span>
                        <span class="focus-tag" data-focus="business_logic">Business Logic</span>
                        <span class="focus-tag" data-focus="info_disclosure">Info Disclosure</span>
                    </div>
                </div>
            </div>
            
            <!-- Launch Panel -->
            <div class="card full-width">
                <div class="card-header">
                    <h2>&#128640; Launch Autonomous Scan</h2>
                </div>
                <div class="card-body">
                    <div id="progressSection" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                        </div>
                        <p id="currentAction" style="color: var(--text-secondary); margin-bottom: 1rem;">Initializing...</p>
                    </div>
                    
                    <div id="configSummary" style="margin-bottom: 1.5rem;">
                        <p style="color: var(--text-secondary);">
                            Review your configuration above, then click the button below to start the autonomous scan.
                            <strong>No further interaction will be required or possible.</strong>
                        </p>
                    </div>
                    
                    <button class="btn btn-primary btn-large fire-btn" id="fireBtn">
                        &#128293; CONFIGURE AND FIRE
                    </button>
                </div>
            </div>
            
            <!-- Findings Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#128030; Findings</h2>
                    <span id="findingsCount" style="color: var(--text-secondary);">0 found</span>
                </div>
                <div class="card-body">
                    <div class="findings-list" id="findingsList">
                        <p style="color: var(--text-secondary); text-align: center; padding: 2rem;">
                            Findings will appear here once the scan starts
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- Logs Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#128196; Activity Log</h2>
                </div>
                <div class="card-body">
                    <div class="logs-container" id="logsContainer">
                        <div class="log-entry">Waiting for scan to start...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // State management
        let selectedModel = 'grok-code-fast-1';
        let selectedFocusAreas = [];
        let scanRunning = false;
        let ws = null;
        
        // DOM elements
        const statusBadge = document.getElementById('statusBadge');
        const statusText = document.getElementById('statusText');
        const fireBtn = document.getElementById('fireBtn');
        const progressSection = document.getElementById('progressSection');
        const progressFill = document.getElementById('progressFill');
        const currentAction = document.getElementById('currentAction');
        const findingsList = document.getElementById('findingsList');
        const findingsCount = document.getElementById('findingsCount');
        const logsContainer = document.getElementById('logsContainer');
        
        // Initialize WebSocket connection
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                addLog('Connected to dashboard server');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }
        
        function handleWebSocketMessage(data) {
            switch (data.type) {
                case 'connected':
                    if (data.status) {
                        updateStatus(data.status);
                    }
                    break;
                case 'config_updated':
                    addLog('Configuration updated');
                    break;
                case 'scan_started':
                    scanRunning = true;
                    updateStatus('running');
                    progressSection.style.display = 'block';
                    fireBtn.disabled = true;
                    fireBtn.textContent = 'Scan Running...';
                    addLog('Autonomous scan started');
                    break;
                case 'progress':
                    updateProgress(data.progress, data.action);
                    break;
                case 'finding':
                    addFinding(data.finding);
                    break;
                case 'log':
                    addLog(data.message);
                    break;
                case 'completed':
                    scanRunning = false;
                    updateStatus('completed');
                    addLog('Scan completed');
                    break;
            }
        }
        
        function updateStatus(status) {
            statusBadge.className = `status-badge status-${status}`;
            const statusLabels = {
                'pending': 'Pending Configuration',
                'configuring': 'Configuring...',
                'running': 'Running Autonomously',
                'completed': 'Completed',
                'failed': 'Failed'
            };
            statusText.textContent = statusLabels[status] || status;
        }
        
        function updateProgress(progress, action) {
            progressFill.style.width = `${progress}%`;
            currentAction.textContent = action;
        }
        
        function addFinding(finding) {
            const html = `
                <div class="finding-item">
                    <div class="finding-header">
                        <span class="finding-title">${escapeHtml(finding.title)}</span>
                        <span class="severity-badge severity-${finding.severity}">${finding.severity}</span>
                    </div>
                    <p style="font-size: 0.875rem; color: var(--text-secondary);">${escapeHtml(finding.description || '')}</p>
                </div>
            `;
            
            if (findingsList.querySelector('p')) {
                findingsList.innerHTML = '';
            }
            findingsList.insertAdjacentHTML('afterbegin', html);
            
            const count = findingsList.querySelectorAll('.finding-item').length;
            findingsCount.textContent = `${count} found`;
        }
        
        function addLog(message) {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = `[${new Date().toISOString()}] ${message}`;
            logsContainer.appendChild(entry);
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Model selection
        document.querySelectorAll('.model-card').forEach(card => {
            card.addEventListener('click', () => {
                document.querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedModel = card.dataset.model;
            });
        });
        
        // Focus area selection
        document.querySelectorAll('.focus-tag').forEach(tag => {
            tag.addEventListener('click', () => {
                tag.classList.toggle('selected');
                const focus = tag.dataset.focus;
                if (selectedFocusAreas.includes(focus)) {
                    selectedFocusAreas = selectedFocusAreas.filter(f => f !== focus);
                } else {
                    selectedFocusAreas.push(focus);
                }
            });
        });
        
        // Provider change
        document.getElementById('aiProvider').addEventListener('change', (e) => {
            const apiKeyGroup = document.getElementById('apiKeyGroup');
            apiKeyGroup.style.display = e.target.value === 'roocode' ? 'none' : 'block';
        });
        
        // Authentication button
        document.getElementById('authBtn').addEventListener('click', async () => {
            try {
                const response = await fetch('/api/roocode/auth', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    addLog('Roo Code authentication successful');
                    alert('Authentication successful!');
                } else {
                    addLog('Authentication failed: ' + (data.error || data.message));
                    alert('Authentication failed: ' + (data.error || data.message));
                }
            } catch (error) {
                addLog('Authentication error: ' + error.message);
                alert('Authentication error: ' + error.message);
            }
        });
        
        // Fire button
        fireBtn.addEventListener('click', async () => {
            const target = document.getElementById('target').value.trim();
            if (!target) {
                alert('Please enter a primary target');
                return;
            }
            
            if (!confirm('Once started, the agent will run autonomously without interruption. Continue?')) {
                return;
            }
            
            fireBtn.disabled = true;
            fireBtn.textContent = 'Saving configuration...';
            
            try {
                // Parse additional targets
                const additionalTargets = document.getElementById('additionalTargets').value
                    .split('\\n')
                    .map(t => t.trim())
                    .filter(t => t.length > 0);
                
                // Save configuration
                const configResponse = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: target,
                        additional_targets: additionalTargets,
                        duration_minutes: parseInt(document.getElementById('duration').value),
                        instructions: document.getElementById('instructions').value,
                        ai_provider: document.getElementById('aiProvider').value,
                        ai_model: selectedModel,
                        api_key: document.getElementById('apiKey').value || null,
                        access_level: document.getElementById('accessLevel').value,
                        allow_package_install: document.getElementById('allowPackageInstall').checked,
                        allow_tool_download: document.getElementById('allowToolDownload').checked,
                        allow_network_config: document.getElementById('allowNetworkConfig').checked,
                        command_timeout: parseInt(document.getElementById('commandTimeout').value),
                        focus_areas: selectedFocusAreas,
                    })
                });
                
                if (!configResponse.ok) {
                    throw new Error('Failed to save configuration');
                }
                
                addLog('Configuration saved');
                fireBtn.textContent = 'Starting scan...';
                
                // Start scan
                const startResponse = await fetch('/api/start', { method: 'POST' });
                if (!startResponse.ok) {
                    throw new Error('Failed to start scan');
                }
                
                addLog('Scan started successfully');
                
            } catch (error) {
                addLog('Error: ' + error.message);
                alert('Error: ' + error.message);
                fireBtn.disabled = false;
                fireBtn.textContent = '&#128293; CONFIGURE AND FIRE';
            }
        });
        
        // Initialize
        connectWebSocket();
    </script>
</body>
</html>'''


def run_dashboard(
    host: str = "0.0.0.0",
    port: int = 8080,
    debug: bool = False,
) -> None:
    """Run the dashboard server."""
    import uvicorn
    
    config = DashboardConfig(host=host, port=port, debug=debug)
    app = create_app(config)
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Strix Dashboard Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    run_dashboard(host=args.host, port=args.port, debug=args.debug)
