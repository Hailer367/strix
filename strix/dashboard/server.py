#!/usr/bin/env python3
"""
Strix Dashboard Server

A FastAPI-based web server that provides a configuration dashboard for
autonomous bug bounty operations through GitHub Actions.

Qwen Code CLI is the sole AI provider.

Features:
- Configure-and-Fire: Set all parameters before starting
- Qwen Code OAuth: Browser-based authentication via qwen.ai
- Real-time WebSocket: Live updates on scan progress
- Advanced Agent Configuration: Fine-tune Strix agent behavior

Authentication Options (Reference: https://github.com/QwenLM/qwen-code):
1. Qwen OAuth (RECOMMENDED): 2,000 requests/day, 60 req/min, no token limits, no regional limits
2. OpenRouter (via qwen-code CLI): 1,000 free requests/day
"""

import asyncio
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import (
    DEFAULT_FOCUS_AREAS,
    QWENCODE_MODELS,
    API_ENDPOINTS,
    PLANNING_DEPTHS,
    MEMORY_STRATEGIES,
    SEVERITY_LEVELS,
    OUTPUT_FORMATS,
    AccessConfig,
    AIConfig,
    AIProvider,
    AgentBehaviorConfig,
    AuthStatus,
    DashboardConfig,
    DashboardState,
    OutputConfig,
    QwenCodeConfig,
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

# Qwen Code CLI configuration
# Reference: https://github.com/QwenLM/qwen-code
# Qwen OAuth: 2,000 requests/day, 60 req/min, no token limits, no regional limits
QWENCODE_AUTH_URL = "https://chat.qwen.ai"
QWENCODE_OPENROUTER_URL = "https://openrouter.ai/api/v1"
QWENCODE_CONFIG_DIR = Path.home() / ".strix"
QWENCODE_CONFIG_FILE = QWENCODE_CONFIG_DIR / "qwencode_config.json"

# Cache for dynamic models
_cached_qwencode_models: dict[str, dict[str, Any]] | None = None
_qwencode_models_cache_time: float = 0

# Global state
dashboard_config = DashboardConfig()
dashboard_state = DashboardState()
connected_websockets: list[WebSocket] = []


def save_qwencode_credentials(
    access_token: str,
    refresh_token: str | None = None,
    expires_at: float | None = None,
    user_email: str | None = None,
    user_id: str | None = None,
    api_endpoint: str | None = None,
    api_provider: str = "qwen_oauth",
) -> None:
    """Save Qwen Code credentials to config file."""
    try:
        QWENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "user_email": user_email,
            "user_id": user_id,
            "api_endpoint": api_endpoint,
            "api_provider": api_provider,
        }
        with open(QWENCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        QWENCODE_CONFIG_FILE.chmod(0o600)
        logger.info("Saved Qwen Code credentials to config")
    except OSError as e:
        logger.warning(f"Failed to save Qwen Code credentials: {e}")


def load_qwencode_credentials() -> dict[str, Any] | None:
    """Load Qwen Code credentials from config file."""
    if QWENCODE_CONFIG_FILE.exists():
        try:
            with open(QWENCODE_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load Qwen Code credentials: {e}")
    return None


async def fetch_qwencode_models(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """
    Fetch available models from Qwen Code API.
    
    Returns default models based on authentication status.
    Reference: https://github.com/QwenLM/qwen-code
    
    Args:
        force_refresh: Force refresh from API even if cache is valid
        
    Returns:
        Dictionary of available models
    """
    global _cached_qwencode_models, _qwencode_models_cache_time
    
    # Use cached models if available and not expired (cache for 30 minutes)
    cache_ttl = 1800
    if (
        not force_refresh
        and _cached_qwencode_models
        and (time.time() - _qwencode_models_cache_time) < cache_ttl
    ):
        return _cached_qwencode_models
    
    # Determine which models to show based on authentication status
    api_provider = dashboard_state.qwencode_api_provider
    
    # Filter models by provider
    filtered_models = {}
    for model_id, model_data in QWENCODE_MODELS.items():
        endpoint = model_data.get("endpoint", "qwen_oauth")
        
        # Show all models if not authenticated yet
        if dashboard_state.auth_status != AuthStatus.AUTHENTICATED:
            filtered_models[model_id] = model_data.copy()
            continue
            
        # Filter by provider - show models matching the auth provider
        if api_provider == "openrouter" and endpoint == "openrouter":
            filtered_models[model_id] = model_data.copy()
        elif api_provider == "qwen_oauth" and endpoint in ("qwen_oauth", "dashscope"):
            filtered_models[model_id] = model_data.copy()
    
    # If authenticated, try to fetch models from API
    if dashboard_state.auth_status == AuthStatus.AUTHENTICATED and dashboard_state.qwencode_access_token:
        api_base = dashboard_state.qwencode_api_endpoint
        
        if api_base:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{api_base}/models",
                        headers={"Authorization": f"Bearer {dashboard_state.qwencode_access_token}"},
                        timeout=30,
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        model_list = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                        
                        for model in model_list:
                            model_id = model.get("id", "")
                            if model_id and ("qwen" in model_id.lower() or "coder" in model_id.lower()):
                                filtered_models[model_id] = {
                                    "name": model_id,
                                    "display_name": model.get("name", model_id),
                                    "description": model.get("description", "Qwen coding model"),
                                    "context_window": model.get("context_length", 131000),
                                    "free": True,
                                    "provider": "qwencode",
                                    "capabilities": ["code", "chat"],
                                    "speed": "fast",
                                    "endpoint": api_provider,
                                }
                        logger.info(f"Fetched {len(filtered_models)} models from Qwen Code API")
            except Exception as e:
                logger.warning(f"Failed to fetch models from API: {e}")
    
    _cached_qwencode_models = filtered_models if filtered_models else QWENCODE_MODELS.copy()
    _qwencode_models_cache_time = time.time()
    return _cached_qwencode_models


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    logger.info("Strix Dashboard starting up...")
    
    # Check for existing Qwen Code credentials
    qwen_creds = load_qwencode_credentials()
    if qwen_creds and qwen_creds.get("access_token"):
        expires_at = qwen_creds.get("expires_at", 0)
        if expires_at == 0 or time.time() < expires_at:
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            dashboard_state.qwencode_access_token = qwen_creds["access_token"]
            dashboard_state.qwencode_refresh_token = qwen_creds.get("refresh_token")
            dashboard_state.qwencode_user_email = qwen_creds.get("user_email")
            dashboard_state.qwencode_user_id = qwen_creds.get("user_id")
            dashboard_state.qwencode_token_expires_at = expires_at
            dashboard_state.qwencode_api_endpoint = qwen_creds.get("api_endpoint")
            dashboard_state.qwencode_api_provider = qwen_creds.get("api_provider", "qwen_oauth")
            logger.info("Loaded existing Qwen Code credentials")
    
    # Check for Qwen Code environment token
    qwen_env_token = os.getenv("QWENCODE_ACCESS_TOKEN") or os.getenv("QWENCODE_API_KEY") or os.getenv("OPENAI_API_KEY")
    qwen_env_base = os.getenv("QWENCODE_API_BASE") or os.getenv("OPENAI_BASE_URL")
    
    if qwen_env_token and dashboard_state.auth_status != AuthStatus.AUTHENTICATED:
        # Determine provider from API base URL
        api_provider = "qwen_oauth"  # Default to qwen_oauth
        api_endpoint = f"{QWENCODE_AUTH_URL}/api/v1"
        
        if qwen_env_base:
            if "openrouter" in qwen_env_base.lower():
                api_provider = "openrouter"
                api_endpoint = QWENCODE_OPENROUTER_URL
            else:
                api_endpoint = qwen_env_base
        
        dashboard_state.auth_status = AuthStatus.AUTHENTICATED
        dashboard_state.qwencode_access_token = qwen_env_token
        dashboard_state.qwencode_api_endpoint = api_endpoint
        dashboard_state.qwencode_api_provider = api_provider
        save_qwencode_credentials(
            qwen_env_token,
            expires_at=time.time() + 3600 * 24 * 365,
            api_endpoint=api_endpoint,
            api_provider=api_provider,
        )
        logger.info(f"Using Qwen Code token from environment (provider: {api_provider})")
    
    yield
    
    logger.info("Strix Dashboard shutting down...")
    for ws in connected_websockets:
        try:
            await ws.close()
        except Exception:
            pass


def create_app(config: DashboardConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global dashboard_config
    
    if config:
        dashboard_config = config
    
    app = FastAPI(
        title="Strix Autonomous Dashboard",
        description="Configuration dashboard for Strix autonomous bug bounty operations - Powered by Qwen Code",
        version="2.1.0",
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
            "auth_status": dashboard_state.auth_status.value,
            "progress": dashboard_state.progress,
            "current_action": dashboard_state.current_action,
            "findings_count": len(dashboard_state.findings),
            "connected_clients": len(connected_websockets),
            "start_time": dashboard_state.start_time.isoformat() if dashboard_state.start_time else None,
            "user_email": dashboard_state.qwencode_user_email,
            "api_provider": dashboard_state.qwencode_api_provider,
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
                scope_includes=data.get("scope_includes", []),
                scope_excludes=data.get("scope_excludes", []),
            )
            
            ai_provider = AIProvider(data.get("ai_provider", "qwencode"))
            qwencode_config = QwenCodeConfig(
                enabled=ai_provider == AIProvider.QWENCODE,
                model=data.get("ai_model", "qwen3-coder-plus"),
                access_token=dashboard_state.qwencode_access_token,
                refresh_token=dashboard_state.qwencode_refresh_token,
                expires_at=dashboard_state.qwencode_token_expires_at,
                user_email=dashboard_state.qwencode_user_email,
                user_id=dashboard_state.qwencode_user_id,
                api_endpoint=dashboard_state.qwencode_api_endpoint,
                api_provider=dashboard_state.qwencode_api_provider,
                auth_status=dashboard_state.auth_status,
            )
            
            ai_config = AIConfig(
                provider=ai_provider,
                model=data.get("ai_model", "qwen3-coder-plus"),
                api_key=data.get("api_key"),
                api_base=data.get("api_base"),
                qwencode=qwencode_config,
                timeout=data.get("timeout", 600),
                max_retries=data.get("max_retries", 3),
                enable_prompt_caching=data.get("enable_prompt_caching", True),
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
                enable_multi_agent=data.get("enable_multi_agent", True),
                max_sub_agents=data.get("max_sub_agents", 5),
                enable_browser_automation=data.get("enable_browser_automation", True),
                enable_proxy_interception=data.get("enable_proxy_interception", True),
                enable_web_search=data.get("enable_web_search", True),
                aggressive_mode=data.get("aggressive_mode", False),
                stealth_mode=data.get("stealth_mode", False),
                rate_limit_rps=data.get("rate_limit_rps", 10),
            )
            
            output_config = OutputConfig(
                format=data.get("output_format", "markdown"),
                severity_threshold=data.get("severity_threshold", "info"),
                notification_webhook=data.get("notification_webhook"),
                save_artifacts=data.get("save_artifacts", True),
                include_screenshots=data.get("include_screenshots", True),
                include_poc=data.get("include_poc", True),
                export_sarif=data.get("export_sarif", False),
            )
            
            behavior_config = AgentBehaviorConfig(
                planning_depth=data.get("planning_depth", "thorough"),
                auto_pivot=data.get("auto_pivot", True),
                chain_attacks=data.get("chain_attacks", True),
                preferred_tools=data.get("preferred_tools", []),
                disabled_tools=data.get("disabled_tools", []),
                memory_strategy=data.get("memory_strategy", "adaptive"),
                context_window_usage=data.get("context_window_usage", 80),
                verbosity=data.get("verbosity", "normal"),
                explain_reasoning=data.get("explain_reasoning", True),
                max_request_size_kb=data.get("max_request_size_kb", 1024),
                max_response_wait_seconds=data.get("max_response_wait_seconds", 60),
                stop_on_critical=data.get("stop_on_critical", False),
            )
            
            scan_config = ScanConfig(
                ai=ai_config,
                access=access_config,
                targets=targets,
                testing=testing_config,
                output=output_config,
                behavior=behavior_config,
                run_id=os.getenv("STRIX_RUN_ID", secrets.token_hex(8)),
                created_at=datetime.now(UTC),
                status=ScanStatus.CONFIGURING,
            )
            
            dashboard_state.config = scan_config
            dashboard_state.status = ScanStatus.CONFIGURING
            
            # Save configuration to file
            config_path = Path(dashboard_config.config_file)
            config_path.write_text(scan_config.model_dump_json(indent=2))
            
            # Also save as environment-compatible format
            env_config = generate_env_config(scan_config)
            env_path = config_path.with_suffix(".env")
            env_path.write_text(env_config)
            
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
        
        # Verify authentication for Qwen Code
        if dashboard_state.config.ai.provider == AIProvider.QWENCODE:
            if dashboard_state.auth_status != AuthStatus.AUTHENTICATED:
                raise HTTPException(
                    status_code=401,
                    detail="Please authenticate with Qwen Code first"
                )
        
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
            
            # Export configuration as environment variables
            export_config_to_env(dashboard_state.config)
            
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
    async def get_models(refresh: bool = False) -> dict[str, Any]:
        """Get available AI models and configuration options."""
        qwencode_models = await fetch_qwencode_models(force_refresh=refresh)
        
        return {
            "qwencode": qwencode_models,
            "authenticated": dashboard_state.auth_status == AuthStatus.AUTHENTICATED,
            "auth_status": dashboard_state.auth_status.value,
            "api_provider": dashboard_state.qwencode_api_provider,
            "api_endpoints": API_ENDPOINTS,
            "focus_areas": DEFAULT_FOCUS_AREAS,
            "planning_depths": PLANNING_DEPTHS,
            "memory_strategies": MEMORY_STRATEGIES,
            "severity_levels": SEVERITY_LEVELS,
            "output_formats": OUTPUT_FORMATS,
        }
    
    @app.get("/api/endpoints")
    async def get_endpoints() -> dict[str, Any]:
        """Get available API endpoints for international users."""
        return {
            "endpoints": API_ENDPOINTS,
            "current_provider": dashboard_state.qwencode_api_provider,
            "recommendation": get_endpoint_recommendation(),
        }
    
    # =========================================================================
    # Qwen Code OAuth Routes
    # =========================================================================
    
    @app.get("/api/qwencode/status")
    async def qwencode_status() -> dict[str, Any]:
        """Get Qwen Code authentication status."""
        return {
            "authenticated": dashboard_state.auth_status == AuthStatus.AUTHENTICATED,
            "status": dashboard_state.auth_status.value,
            "user_email": dashboard_state.qwencode_user_email,
            "user_id": dashboard_state.qwencode_user_id,
            "expires_at": dashboard_state.qwencode_token_expires_at,
            "api_endpoint": dashboard_state.qwencode_api_endpoint,
            "api_provider": dashboard_state.qwencode_api_provider,
        }
    
    @app.get("/api/qwencode/login")
    async def qwencode_login_redirect(request: Request) -> dict[str, Any]:
        """Get the Qwen Code OAuth login URL.
        
        Qwen OAuth provides:
        - 2,000 free requests per day
        - 60 requests per minute rate limit
        - NO token limits, NO regional limits
        - Automatic credential refresh
        
        Reference: https://github.com/QwenLM/qwen-code
        """
        state = secrets.token_urlsafe(16)
        dashboard_state.oauth_state = state
        dashboard_state.auth_status = AuthStatus.AUTHENTICATING
        
        host = request.headers.get("host", f"localhost:{dashboard_config.port}")
        scheme = request.headers.get("x-forwarded-proto", "http")
        callback_url = f"{scheme}://{host}/api/qwencode/callback"
        
        # Qwen Code CLI uses qwen.ai for OAuth authentication
        auth_url = f"{QWENCODE_AUTH_URL}/?redirect_uri={callback_url}&state={state}&app=strix"
        
        await broadcast_update({
            "type": "auth_started",
            "status": "authenticating",
        })
        
        return {
            "auth_url": auth_url,
            "state": state,
            "callback_url": callback_url,
            "instructions": "Sign in with your qwen.ai account to get 2,000 free requests per day (no regional limits!)",
        }
    
    @app.get("/api/qwencode/callback", response_model=None)
    async def qwencode_callback(
        request: Request,
        token: str | None = None,
        access_token: str | None = None,
        session_token: str | None = None,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ) -> HTMLResponse:
        """Handle Qwen Code OAuth callback."""
        global _cached_qwencode_models, _qwencode_models_cache_time
        
        if error:
            dashboard_state.auth_status = AuthStatus.FAILED
            await broadcast_update({"type": "auth_failed", "error": error})
            return HTMLResponse(content=get_auth_result_html(False, error), status_code=400)
        
        # Handle multiple token parameter names
        received_token = token or access_token or session_token or code
        
        if received_token:
            dashboard_state.qwencode_access_token = received_token
            dashboard_state.qwencode_token_expires_at = time.time() + 3600 * 24 * 30  # 30 days
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            dashboard_state.qwencode_api_provider = "qwen_oauth"
            # Qwen OAuth uses chat.qwen.ai API endpoint
            dashboard_state.qwencode_api_endpoint = f"{QWENCODE_AUTH_URL}/api/v1"
            
            save_qwencode_credentials(
                access_token=received_token,
                expires_at=dashboard_state.qwencode_token_expires_at,
                api_endpoint=dashboard_state.qwencode_api_endpoint,
                api_provider="qwen_oauth",
            )
            
            os.environ["QWENCODE_ACCESS_TOKEN"] = received_token
            os.environ["OPENAI_API_KEY"] = received_token
            os.environ["OPENAI_BASE_URL"] = dashboard_state.qwencode_api_endpoint
            
            _cached_qwencode_models = None
            _qwencode_models_cache_time = 0
            
            await broadcast_update({
                "type": "auth_success",
                "user_email": dashboard_state.qwencode_user_email,
                "api_provider": "qwen_oauth",
            })
            
            return HTMLResponse(content=get_auth_result_html(True), status_code=200)
        
        return HTMLResponse(content=get_auth_result_html(False, "No token received"), status_code=400)
    
    @app.post("/api/qwencode/logout")
    async def qwencode_logout() -> dict[str, Any]:
        """Log out from Qwen Code."""
        dashboard_state.auth_status = AuthStatus.NOT_AUTHENTICATED
        dashboard_state.qwencode_access_token = None
        dashboard_state.qwencode_refresh_token = None
        dashboard_state.qwencode_user_email = None
        dashboard_state.qwencode_user_id = None
        dashboard_state.qwencode_token_expires_at = None
        dashboard_state.qwencode_api_endpoint = None
        dashboard_state.qwencode_api_provider = "qwen_oauth"
        
        # Remove environment variables
        for var in ["QWENCODE_ACCESS_TOKEN", "QWENCODE_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL"]:
            if var in os.environ:
                del os.environ[var]
        
        if QWENCODE_CONFIG_FILE.exists():
            try:
                QWENCODE_CONFIG_FILE.unlink()
            except OSError:
                pass
        
        await broadcast_update({"type": "auth_logout"})
        return {"success": True, "message": "Logged out from Qwen Code"}
    
    @app.post("/api/qwencode/set-token")
    async def qwencode_set_token(request: Request) -> dict[str, Any]:
        """Manually set Qwen Code API token.
        
        This is used for:
        1. OpenRouter API key (via qwen-code CLI for 1,000 requests/day)
        2. Manual token from Qwen Code CLI
        
        IMPORTANT: For OpenRouter, must go through qwen-code CLI, not directly to OpenRouter
        Reference: https://github.com/QwenLM/qwen-code
        """
        global _cached_qwencode_models, _qwencode_models_cache_time
        
        try:
            data = await request.json()
            token = data.get("token")
            api_endpoint = data.get("api_endpoint")
            api_provider = data.get("api_provider", "openrouter")
            
            if not token:
                raise HTTPException(status_code=400, detail="Token is required")
            
            # Only support qwen_oauth and openrouter
            if api_provider not in ("qwen_oauth", "openrouter"):
                api_provider = "openrouter"
            
            # Set endpoint based on provider
            if api_provider == "openrouter" or (api_endpoint and "openrouter" in api_endpoint.lower()):
                api_provider = "openrouter"
                api_endpoint = QWENCODE_OPENROUTER_URL
            else:
                # Default to qwen_oauth
                api_provider = "qwen_oauth"
                api_endpoint = f"{QWENCODE_AUTH_URL}/api/v1"
            
            dashboard_state.qwencode_access_token = token
            dashboard_state.qwencode_token_expires_at = time.time() + 3600 * 24 * 365  # 1 year
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            dashboard_state.qwencode_api_endpoint = api_endpoint
            dashboard_state.qwencode_api_provider = api_provider
            
            save_qwencode_credentials(
                access_token=token,
                expires_at=dashboard_state.qwencode_token_expires_at,
                api_endpoint=api_endpoint,
                api_provider=api_provider,
            )
            
            # Set environment variables for Strix
            os.environ["QWENCODE_ACCESS_TOKEN"] = token
            os.environ["OPENAI_API_KEY"] = token
            os.environ["OPENAI_BASE_URL"] = api_endpoint
            
            _cached_qwencode_models = None
            _qwencode_models_cache_time = 0
            
            await broadcast_update({
                "type": "auth_success",
                "user_email": None,
                "api_provider": api_provider,
            })
            
            return {
                "success": True,
                "message": f"Qwen Code token set successfully (provider: {api_provider})",
                "api_provider": api_provider,
                "api_endpoint": api_endpoint,
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    # =========================================================================
    # WebSocket Route
    # =========================================================================
    
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
                "auth_status": dashboard_state.auth_status.value,
                "user_email": dashboard_state.qwencode_user_email,
                "api_provider": dashboard_state.qwencode_api_provider,
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
        except Exception:
            if websocket in connected_websockets:
                connected_websockets.remove(websocket)
    
    return app


async def broadcast_update(data: dict[str, Any]) -> None:
    """Broadcast update to all connected WebSocket clients."""
    for ws in connected_websockets[:]:
        try:
            await ws.send_json(data)
        except Exception:
            connected_websockets.remove(ws)


def add_finding(finding: dict[str, Any]) -> None:
    """Add a vulnerability finding."""
    dashboard_state.findings.append(finding)
    asyncio.create_task(broadcast_update({
        "type": "finding",
        "finding": finding,
    }))


def add_log(message: str) -> None:
    """Add a log entry."""
    timestamp = datetime.now(UTC).isoformat()
    log_entry = f"[{timestamp}] {message}"
    dashboard_state.logs.append(log_entry)
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


def get_endpoint_recommendation() -> dict[str, Any]:
    """Get recommendation for API endpoint."""
    return {
        "recommended": "qwen_oauth",
        "reason": "Qwen OAuth provides 2,000 free requests/day, 60 req/min, no token limits, no regional limits",
        "alternatives": {
            "openrouter": {
                "description": "OpenRouter via qwen-code CLI - 1,000 free requests/day",
                "use_case": "When you prefer API key authentication",
            },
        },
        "reference": "https://github.com/QwenLM/qwen-code",
    }


def generate_env_config(config: ScanConfig) -> str:
    """Generate environment variables configuration."""
    lines = [
        "# Strix Dashboard Generated Configuration",
        f"# Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "# AI Configuration - Qwen Code",
    ]
    
    if config.ai.provider == AIProvider.QWENCODE:
        lines.extend([
            "STRIX_USE_QWENCODE=true",
            f"STRIX_LLM=qwencode/{config.ai.model}",
        ])
        if config.ai.qwencode.access_token:
            lines.append(f"QWENCODE_ACCESS_TOKEN={config.ai.qwencode.access_token}")
            lines.append(f"OPENAI_API_KEY={config.ai.qwencode.access_token}")
        if config.ai.qwencode.api_endpoint:
            lines.append(f"QWENCODE_API_BASE={config.ai.qwencode.api_endpoint}")
            lines.append(f"OPENAI_BASE_URL={config.ai.qwencode.api_endpoint}")
        if config.ai.model:
            lines.append(f"OPENAI_MODEL={config.ai.model}")
    else:
        lines.append(f"STRIX_LLM={config.ai.provider.value}/{config.ai.model}")
        if config.ai.api_key:
            lines.append(f"LLM_API_KEY={config.ai.api_key}")
        if config.ai.api_base:
            lines.append(f"LLM_API_BASE={config.ai.api_base}")
    
    lines.extend([
        "",
        "# Access Configuration",
        f"STRIX_ACCESS_LEVEL={config.access.level}",
        f"STRIX_ROOT_ACCESS={'true' if config.access.level == 'root' else 'false'}",
        f"STRIX_ALLOW_PACKAGE_INSTALL={'true' if config.access.allow_package_install else 'false'}",
        f"STRIX_ALLOW_TOOL_DOWNLOAD={'true' if config.access.allow_tool_download else 'false'}",
        f"STRIX_ALLOW_NETWORK_CONFIG={'true' if config.access.allow_network_config else 'false'}",
        f"STRIX_ALLOW_SYSTEM_MOD={'true' if config.access.allow_system_modification else 'false'}",
        f"STRIX_COMMAND_TIMEOUT={config.access.command_timeout}",
        "",
        "# Testing Configuration",
        f"STRIX_MAX_ITERATIONS={config.testing.max_iterations}",
        f"STRIX_DURATION_MINUTES={config.testing.duration_minutes}",
        f"LLM_TIMEOUT={config.ai.timeout}",
    ])
    
    return "\n".join(lines)


def export_config_to_env(config: ScanConfig) -> None:
    """Export configuration to environment variables."""
    if config.ai.provider == AIProvider.QWENCODE:
        os.environ["STRIX_USE_QWENCODE"] = "true"
        os.environ["STRIX_LLM"] = f"qwencode/{config.ai.model}"
        if config.ai.qwencode.access_token:
            os.environ["QWENCODE_ACCESS_TOKEN"] = config.ai.qwencode.access_token
            os.environ["OPENAI_API_KEY"] = config.ai.qwencode.access_token
        if config.ai.qwencode.api_endpoint:
            os.environ["QWENCODE_API_BASE"] = config.ai.qwencode.api_endpoint
            os.environ["OPENAI_BASE_URL"] = config.ai.qwencode.api_endpoint
        if config.ai.model:
            os.environ["OPENAI_MODEL"] = config.ai.model
    else:
        os.environ["STRIX_LLM"] = f"{config.ai.provider.value}/{config.ai.model}"
        if config.ai.api_key:
            os.environ["LLM_API_KEY"] = config.ai.api_key
        if config.ai.api_base:
            os.environ["LLM_API_BASE"] = config.ai.api_base
    
    os.environ["STRIX_ACCESS_LEVEL"] = config.access.level
    os.environ["STRIX_ROOT_ACCESS"] = "true" if config.access.level == "root" else "false"
    os.environ["STRIX_COMMAND_TIMEOUT"] = str(config.access.command_timeout)
    os.environ["LLM_TIMEOUT"] = str(config.ai.timeout)


def get_auth_result_html(success: bool, error: str | None = None) -> str:
    """Generate HTML page for auth callback result."""
    if success:
        return '''<!DOCTYPE html>
<html>
<head>
    <title>Strix - Qwen Code Authentication Successful</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center; height: 100vh;
               margin: 0; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
        .container { text-align: center; padding: 40px; background: rgba(255,255,255,0.1);
                     border-radius: 16px; backdrop-filter: blur(10px); max-width: 400px; }
        h1 { color: #22c55e; margin-bottom: 16px; }
        p { color: #e5e5e5; margin: 10px 0; }
        .icon { font-size: 64px; margin-bottom: 20px; }
        .success { color: #22c55e; }
        .btn { display: inline-block; margin-top: 20px; padding: 12px 24px;
               background: #22c55e; color: #000; text-decoration: none;
               border-radius: 8px; font-weight: 600; cursor: pointer; }
        .btn:hover { background: #16a34a; }
        .info { color: #94a3b8; font-size: 0.875rem; margin-top: 15px; }
    </style>
    <script>
        (function() {
            if (window.opener) {
                try {
                    window.opener.postMessage({ type: 'qwencode_auth_success' }, '*');
                    setTimeout(() => window.close(), 1500);
                } catch (e) {}
            } else {
                setTimeout(() => window.location.href = '/', 2000);
            }
        })();
        function goToDashboard() { window.location.href = '/'; }
    </script>
</head>
<body>
    <div class="container">
        <div class="icon">&#129302;</div>
        <h1>Authentication Successful!</h1>
        <p class="success">&#10003; Connected to Qwen Code</p>
        <p>2,000 free requests per day - 60 requests per minute</p>
        <p class="info">No token limits!</p>
        <button class="btn" onclick="goToDashboard()">Go to Dashboard</button>
    </div>
</body>
</html>'''
    else:
        return f'''<!DOCTYPE html>
<html>
<head>
    <title>Strix - Qwen Code Authentication Failed</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center; height: 100vh;
               margin: 0; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }}
        .container {{ text-align: center; padding: 40px; background: rgba(255,255,255,0.1);
                     border-radius: 16px; backdrop-filter: blur(10px); max-width: 450px; }}
        h1 {{ color: #ef4444; margin-bottom: 16px; }}
        p {{ color: #e5e5e5; margin: 10px 0; }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        .error {{ color: #fca5a5; background: rgba(239, 68, 68, 0.2);
                 padding: 10px 15px; border-radius: 8px; margin: 15px 0; word-break: break-word; }}
        .btn {{ display: inline-block; margin-top: 20px; padding: 12px 24px;
               background: #3b82f6; color: #fff; text-decoration: none;
               border-radius: 8px; font-weight: 600; cursor: pointer; margin: 5px; }}
        .btn:hover {{ background: #2563eb; }}
        .alternative {{ background: rgba(59, 130, 246, 0.1); border: 1px solid #3b82f6;
                       border-radius: 8px; padding: 15px; margin-top: 20px; text-align: left; }}
        .alternative h3 {{ color: #3b82f6; margin: 0 0 10px 0; font-size: 0.875rem; }}
        .alternative p {{ font-size: 0.8125rem; color: #94a3b8; margin: 5px 0; }}
    </style>
    <script>
        if (window.opener) {{
            try {{ window.opener.postMessage({{ type: 'qwencode_auth_failed', error: '{error or "Unknown error"}' }}, '*'); }} catch (e) {{}}
        }}
        function tryAgain() {{ window.opener ? window.close() : window.location.href = '/'; }}
        function goToDashboard() {{ window.location.href = '/'; }}
    </script>
</head>
<body>
    <div class="container">
        <div class="icon">&#10060;</div>
        <h1>Authentication Failed</h1>
        <p class="error">{error or "Unknown error occurred"}</p>
        <p>Please try again or check your internet connection.</p>
        
        <div class="alternative">
            <h3>&#127760; International Users</h3>
            <p>Use OpenRouter (1,000 free requests/day worldwide) or DashScope International.</p>
            <p>Go to dashboard and enter your API key manually.</p>
        </div>
        
        <button class="btn" onclick="tryAgain()">Try Again</button>
        <button class="btn" onclick="goToDashboard()">Go to Dashboard</button>
    </div>
</body>
</html>'''


def get_dashboard_html() -> str:
    """Generate the dashboard HTML - Qwen Code as sole AI provider."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Strix Autonomous Dashboard - Powered by Qwen Code</title>
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
            --accent-purple: #8b5cf6;
            --accent-qwen: #6366f1;
            --border-color: #475569;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }
        
        .container { max-width: 1600px; margin: 0 auto; padding: 1.5rem; }
        
        header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 1rem 2rem; background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap; gap: 1rem;
        }
        
        .logo { display: flex; align-items: center; gap: 1rem; }
        .logo-icon { font-size: 2rem; }
        .logo-text h1 { font-size: 1.25rem; color: var(--accent-qwen); }
        .logo-text p { font-size: 0.75rem; color: var(--text-secondary); }
        
        .header-status { display: flex; align-items: center; gap: 1rem; }
        
        .auth-status {
            display: flex; align-items: center; gap: 0.5rem;
            padding: 0.5rem 1rem; background: var(--bg-tertiary);
            border-radius: 8px; font-size: 0.875rem;
        }
        .auth-status.authenticated { background: rgba(34, 197, 94, 0.2); border: 1px solid var(--accent-primary); }
        .auth-status.not-authenticated { background: rgba(245, 158, 11, 0.2); border: 1px solid var(--accent-warning); }
        
        .status-badge {
            display: inline-flex; align-items: center; gap: 0.5rem;
            padding: 0.5rem 1rem; border-radius: 9999px;
            font-size: 0.875rem; font-weight: 500;
        }
        .status-pending { background: var(--bg-tertiary); }
        .status-running { background: var(--accent-primary); color: #000; }
        .status-completed { background: var(--accent-primary); color: #000; }
        .status-failed { background: var(--accent-danger); }
        
        .main-content {
            display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem; margin-top: 1.5rem;
        }
        @media (max-width: 1200px) { .main-content { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 768px) { .main-content { grid-template-columns: 1fr; } }
        
        .card {
            background: var(--bg-secondary); border-radius: 1rem;
            border: 1px solid var(--border-color); overflow: hidden;
        }
        .card-header {
            padding: 1rem 1.25rem; border-bottom: 1px solid var(--border-color);
            display: flex; justify-content: space-between; align-items: center;
        }
        .card-header h2 { font-size: 1rem; font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
        .card-body { padding: 1.25rem; }
        
        .form-group { margin-bottom: 1.25rem; }
        .form-group:last-child { margin-bottom: 0; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-size: 0.8125rem; color: var(--text-secondary); font-weight: 500; }
        .form-group input, .form-group select, .form-group textarea {
            width: 100%; padding: 0.625rem 0.875rem; background: var(--bg-tertiary);
            border: 1px solid var(--border-color); border-radius: 0.5rem;
            color: var(--text-primary); font-size: 0.875rem;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            outline: none; border-color: var(--accent-qwen);
        }
        .form-group textarea { min-height: 80px; resize: vertical; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        
        .checkbox-group { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
        .checkbox-group input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
        .checkbox-group label { margin: 0; cursor: pointer; font-size: 0.8125rem; }
        
        .btn {
            display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
            padding: 0.625rem 1.25rem; border-radius: 0.5rem;
            font-size: 0.875rem; font-weight: 500; cursor: pointer;
            transition: all 0.2s; border: none;
        }
        .btn-primary { background: var(--accent-qwen); color: #fff; }
        .btn-primary:hover { background: #4f46e5; }
        .btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-color); }
        .btn-secondary:hover { background: var(--border-color); }
        .btn-danger { background: var(--accent-danger); color: #fff; }
        .btn-block { width: 100%; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .fire-btn {
            width: 100%; margin-top: 1rem;
            background: linear-gradient(135deg, var(--accent-qwen), var(--accent-purple));
            font-size: 1.125rem; padding: 1rem; color: #fff;
        }
        .fire-btn:hover:not(:disabled) { transform: scale(1.02); }
        
        .model-cards { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }
        .model-card {
            padding: 0.875rem; background: var(--bg-tertiary); border-radius: 0.5rem;
            cursor: pointer; border: 2px solid transparent; transition: all 0.2s;
        }
        .model-card:hover { border-color: var(--accent-qwen); }
        .model-card.selected { border-color: var(--accent-primary); background: rgba(34, 197, 94, 0.1); }
        .model-card h3 { font-size: 0.875rem; margin-bottom: 0.25rem; }
        .model-card p { font-size: 0.75rem; color: var(--text-secondary); }
        .model-card .model-meta { display: flex; gap: 0.5rem; margin-top: 0.5rem; flex-wrap: wrap; }
        .model-tag { font-size: 0.625rem; padding: 0.125rem 0.375rem; background: var(--bg-primary); border-radius: 4px; color: var(--text-secondary); }
        .model-tag.free { background: rgba(34, 197, 94, 0.2); color: var(--accent-primary); }
        .model-tag.intl { background: rgba(59, 130, 246, 0.2); color: var(--accent-secondary); }
        
        .focus-areas { display: flex; flex-wrap: wrap; gap: 0.375rem; }
        .focus-tag {
            padding: 0.25rem 0.625rem; background: var(--bg-tertiary);
            border-radius: 9999px; font-size: 0.6875rem; cursor: pointer;
            border: 1px solid var(--border-color); transition: all 0.2s;
        }
        .focus-tag:hover { border-color: var(--accent-secondary); }
        .focus-tag.selected { background: var(--accent-secondary); border-color: var(--accent-secondary); }
        
        .findings-list { max-height: 350px; overflow-y: auto; }
        .finding-item { padding: 0.875rem; border-bottom: 1px solid var(--border-color); }
        .finding-item:last-child { border-bottom: none; }
        .finding-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
        .finding-title { font-weight: 500; font-size: 0.875rem; }
        .severity-badge { padding: 0.125rem 0.5rem; border-radius: 0.25rem; font-size: 0.6875rem; font-weight: 600; text-transform: uppercase; }
        .severity-critical { background: #dc2626; }
        .severity-high { background: #ea580c; }
        .severity-medium { background: #d97706; }
        .severity-low { background: #2563eb; }
        .severity-info { background: #6b7280; }
        
        .progress-bar { height: 6px; background: var(--bg-tertiary); border-radius: 9999px; overflow: hidden; margin-bottom: 0.75rem; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent-qwen), var(--accent-purple)); transition: width 0.3s; }
        
        .logs-container {
            background: var(--bg-primary); border-radius: 0.5rem; padding: 0.75rem;
            max-height: 250px; overflow-y: auto;
            font-family: 'Fira Code', 'Monaco', monospace; font-size: 0.75rem;
        }
        .log-entry { padding: 0.25rem 0; color: var(--text-secondary); word-break: break-all; }
        
        .full-width { grid-column: 1 / -1; }
        .col-span-2 { grid-column: span 2; }
        
        .warning-notice, .info-notice {
            display: flex; align-items: flex-start; gap: 0.75rem;
            padding: 0.875rem; border-radius: 0.5rem; margin-bottom: 1.25rem;
        }
        .warning-notice { background: rgba(245, 158, 11, 0.1); border: 1px solid var(--accent-warning); }
        .warning-notice p { font-size: 0.8125rem; color: var(--accent-warning); }
        .info-notice { background: rgba(99, 102, 241, 0.1); border: 1px solid var(--accent-qwen); }
        .info-notice p { font-size: 0.8125rem; color: var(--accent-qwen); }
        
        .section-divider { height: 1px; background: var(--border-color); margin: 1.25rem 0; }
        .section-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary); margin-bottom: 0.75rem; }
        
        .slider-container { display: flex; align-items: center; gap: 1rem; }
        .slider-container input[type="range"] { flex: 1; -webkit-appearance: none; height: 6px; background: var(--bg-tertiary); border-radius: 3px; }
        .slider-container input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; width: 16px; height: 16px; background: var(--accent-qwen); border-radius: 50%; cursor: pointer; }
        .slider-value { min-width: 40px; text-align: right; font-size: 0.875rem; color: var(--accent-qwen); }
        
        .tabs { display: flex; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem; }
        .tab { padding: 0.75rem 1rem; cursor: pointer; font-size: 0.8125rem; color: var(--text-secondary); border-bottom: 2px solid transparent; transition: all 0.2s; }
        .tab:hover { color: var(--text-primary); }
        .tab.active { color: var(--accent-qwen); border-bottom-color: var(--accent-qwen); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .endpoint-card {
            padding: 0.75rem; background: var(--bg-tertiary); border-radius: 0.5rem;
            margin-bottom: 0.5rem; cursor: pointer; border: 2px solid transparent;
        }
        .endpoint-card:hover { border-color: var(--accent-qwen); }
        .endpoint-card.selected { border-color: var(--accent-primary); background: rgba(34, 197, 94, 0.1); }
        .endpoint-card h4 { font-size: 0.8125rem; margin-bottom: 0.25rem; }
        .endpoint-card p { font-size: 0.6875rem; color: var(--text-secondary); }
        
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <span class="logo-icon">&#129417;</span>
            <div class="logo-text">
                <h1>Strix Autonomous Dashboard</h1>
                <p>Powered by Qwen Code - Bug Bounty Automation</p>
            </div>
        </div>
        <div class="header-status">
            <div id="authStatus" class="auth-status not-authenticated">
                <span id="authIcon">&#128274;</span>
                <span id="authText">Not Authenticated</span>
            </div>
            <div id="statusBadge" class="status-badge status-pending">
                <span id="statusDot">&#9679;</span>
                <span id="statusText">Pending Configuration</span>
            </div>
        </div>
    </header>
    
    <div class="container">
        <div class="main-content">
            <!-- Authentication & AI Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#129302; Qwen Code Authentication</h2>
                </div>
                <div class="card-body">
                    <div class="info-notice">
                        <span>&#128161;</span>
                        <p><strong>Qwen Code</strong> provides free AI models. Login with your qwen.ai account for 2,000 free requests/day, or use OpenRouter for international access.</p>
                    </div>
                    
                    <div class="tabs">
                        <div class="tab active" data-tab="oauth">Qwen OAuth</div>
                        <div class="tab" data-tab="apikey">API Key</div>
                    </div>
                    
                    <div id="oauthTab" class="tab-content active">
                        <div class="info-notice" id="oauthInfo">
                            <span>&#128161;</span>
                            <p><strong>Recommended:</strong> Qwen OAuth provides 2,000 free requests/day, 60 req/min, with NO token limits and NO regional restrictions!</p>
                        </div>
                        
                        <button class="btn btn-primary btn-block" id="loginBtn">
                            &#128274; Login with qwen.ai Account
                        </button>
                        <button class="btn btn-danger btn-block hidden" id="logoutBtn">
                            &#128275; Logout
                        </button>
                        
                        <p style="margin-top: 1rem; font-size: 0.75rem; color: var(--text-secondary); text-align: center;">
                            Free tier: 2,000 requests/day | 60 requests/min | No token limits
                        </p>
                    </div>
                    
                    <div id="apikeyTab" class="tab-content">
                        <div class="section-title">Select API Provider</div>
                        <div id="endpointCards">
                            <div class="endpoint-card selected" data-provider="openrouter" data-endpoint="https://openrouter.ai/api/v1">
                                <h4>&#127760; OpenRouter (via qwen-code)</h4>
                                <p>1,000 free requests/day - Use when you have an OpenRouter API key</p>
                            </div>
                        </div>
                        
                        <div class="form-group" style="margin-top: 1rem;">
                            <label>API Key</label>
                            <input type="password" id="qwenApiKey" placeholder="Enter your API key">
                        </div>
                        <div class="form-group">
                            <label>API Endpoint (auto-filled based on selection)</label>
                            <input type="text" id="qwenApiEndpoint" placeholder="https://openrouter.ai/api/v1">
                        </div>
                        <button class="btn btn-primary btn-block" id="setApiKeyBtn">
                            &#128273; Set API Key
                        </button>
                    </div>
                    
                    <div class="section-divider"></div>
                    
                    <div class="section-title">Select Model</div>
                    <div class="model-cards" id="modelCards">
                        <div class="model-card" style="text-align: center; color: var(--text-secondary);">
                            <p>Loading models...</p>
                        </div>
                    </div>
                    <button class="btn btn-secondary btn-block" id="refreshModelsBtn" style="margin-top: 0.75rem;">
                        &#128260; Refresh Models
                    </button>
                </div>
            </div>
            
            <!-- Target Configuration -->
            <div class="card">
                <div class="card-header">
                    <h2>&#127919; Target Configuration</h2>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label>Primary Target *</label>
                        <input type="text" id="target" placeholder="https://example.com or https://github.com/org/repo" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Additional Targets (one per line)</label>
                        <textarea id="additionalTargets" placeholder="https://api.example.com&#10;https://staging.example.com"></textarea>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Duration (minutes)</label>
                            <input type="number" id="duration" value="60" min="5" max="480">
                        </div>
                        <div class="form-group">
                            <label>Max Iterations</label>
                            <input type="number" id="maxIterations" value="300" min="10" max="1000">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Custom Instructions</label>
                        <textarea id="instructions" placeholder="Focus on authentication vulnerabilities. Test account: user@test.com / password123"></textarea>
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
                    
                    <div class="section-title">Permissions</div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="allowPackageInstall" checked>
                        <label for="allowPackageInstall">Allow package installation</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="allowToolDownload" checked>
                        <label for="allowToolDownload">Allow tool downloads</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="allowNetworkConfig" checked>
                        <label for="allowNetworkConfig">Allow network configuration</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="allowSystemMod" checked>
                        <label for="allowSystemMod">Allow system modification</label>
                    </div>
                    
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Command Timeout (seconds)</label>
                        <input type="number" id="commandTimeout" value="600" min="60" max="3600">
                    </div>
                </div>
            </div>
            
            <!-- Agent Behavior Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#129504; Agent Behavior</h2>
                </div>
                <div class="card-body">
                    <div class="form-group">
                        <label>Planning Depth</label>
                        <select id="planningDepth">
                            <option value="quick">Quick - Fast reconnaissance</option>
                            <option value="balanced">Balanced - Moderate analysis</option>
                            <option value="thorough" selected>Thorough - Deep analysis</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Memory Strategy</label>
                        <select id="memoryStrategy">
                            <option value="minimal">Minimal - Faster</option>
                            <option value="adaptive" selected>Adaptive - Auto-adjusts</option>
                            <option value="full">Full - Most thorough</option>
                        </select>
                    </div>
                    
                    <div class="section-title">Capabilities</div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="enableMultiAgent" checked>
                        <label for="enableMultiAgent">Multi-agent collaboration</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="enableBrowser" checked>
                        <label for="enableBrowser">Browser automation</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="enableProxy" checked>
                        <label for="enableProxy">Proxy interception</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="enableWebSearch" checked>
                        <label for="enableWebSearch">Web search (requires API key)</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="chainAttacks" checked>
                        <label for="chainAttacks">Chain attacks</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="autoPivot" checked>
                        <label for="autoPivot">Auto-pivot on findings</label>
                    </div>
                    
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Rate Limit (requests/sec)</label>
                        <div class="slider-container">
                            <input type="range" id="rateLimit" min="1" max="50" value="10">
                            <span class="slider-value" id="rateLimitValue">10</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Focus Areas Panel -->
            <div class="card">
                <div class="card-header">
                    <h2>&#128270; Focus Areas</h2>
                </div>
                <div class="card-body">
                    <p style="margin-bottom: 0.75rem; color: var(--text-secondary); font-size: 0.8125rem;">
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
                        <span class="focus-tag" data-focus="api_security">API Security</span>
                    </div>
                </div>
            </div>
            
            <!-- Output Configuration -->
            <div class="card">
                <div class="card-header">
                    <h2>&#128196; Output Configuration</h2>
                </div>
                <div class="card-body">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Report Format</label>
                            <select id="outputFormat">
                                <option value="markdown" selected>Markdown</option>
                                <option value="json">JSON</option>
                                <option value="html">HTML</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Min Severity</label>
                            <select id="severityThreshold">
                                <option value="info" selected>Info</option>
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                                <option value="critical">Critical</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="checkbox-group">
                        <input type="checkbox" id="saveArtifacts" checked>
                        <label for="saveArtifacts">Save artifacts</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="includeScreenshots" checked>
                        <label for="includeScreenshots">Include screenshots</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="includePoc" checked>
                        <label for="includePoc">Include PoC code</label>
                    </div>
                    
                    <div class="form-group" style="margin-top: 1rem;">
                        <label>Notification Webhook (optional)</label>
                        <input type="text" id="webhook" placeholder="https://hooks.slack.com/...">
                    </div>
                </div>
            </div>
            
            <!-- Launch Panel -->
            <div class="card full-width">
                <div class="card-header">
                    <h2>&#128640; Launch Autonomous Scan</h2>
                </div>
                <div class="card-body">
                    <div class="warning-notice">
                        <span>&#9888;</span>
                        <p><strong>Configure and Fire:</strong> Once started, the agent runs autonomously without interruption. Review all configuration options before launching.</p>
                    </div>
                    
                    <div id="progressSection" style="display: none;">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                        </div>
                        <p id="currentAction" style="color: var(--text-secondary); margin-bottom: 1rem; font-size: 0.875rem;">Initializing...</p>
                    </div>
                    
                    <button class="btn btn-primary fire-btn" id="fireBtn">
                        &#128293; CONFIGURE AND FIRE
                    </button>
                </div>
            </div>
            
            <!-- Findings Panel -->
            <div class="card col-span-2">
                <div class="card-header">
                    <h2>&#128030; Findings</h2>
                    <span id="findingsCount" style="color: var(--text-secondary); font-size: 0.875rem;">0 found</span>
                </div>
                <div class="card-body">
                    <div class="findings-list" id="findingsList">
                        <p style="color: var(--text-secondary); text-align: center; padding: 2rem; font-size: 0.875rem;">
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
        let selectedModel = 'qwen3-coder-plus';
        let selectedFocusAreas = [];
        let selectedProvider = 'openrouter';
        let selectedEndpoint = 'https://openrouter.ai/api/v1';
        let scanRunning = false;
        let isAuthenticated = false;
        let ws = null;
        let authWindow = null;
        let availableModels = {};
        
        // DOM elements
        const authStatus = document.getElementById('authStatus');
        const authIcon = document.getElementById('authIcon');
        const authText = document.getElementById('authText');
        const statusBadge = document.getElementById('statusBadge');
        const statusText = document.getElementById('statusText');
        const fireBtn = document.getElementById('fireBtn');
        const loginBtn = document.getElementById('loginBtn');
        const logoutBtn = document.getElementById('logoutBtn');
        const progressSection = document.getElementById('progressSection');
        const progressFill = document.getElementById('progressFill');
        const currentAction = document.getElementById('currentAction');
        const findingsList = document.getElementById('findingsList');
        const findingsCount = document.getElementById('findingsCount');
        const logsContainer = document.getElementById('logsContainer');
        const modelCardsContainer = document.getElementById('modelCards');
        
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + 'Tab').classList.add('active');
            });
        });
        
        // Endpoint card selection
        document.querySelectorAll('.endpoint-card').forEach(card => {
            card.addEventListener('click', () => {
                document.querySelectorAll('.endpoint-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedProvider = card.dataset.provider;
                selectedEndpoint = card.dataset.endpoint;
                document.getElementById('qwenApiEndpoint').value = selectedEndpoint;
            });
        });
        
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
                    if (data.status) updateStatus(data.status);
                    if (data.auth_status) updateAuthStatus(data.auth_status === 'authenticated', data.user_email);
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
                case 'auth_started':
                    updateAuthStatus(false, null, 'authenticating');
                    break;
                case 'auth_success':
                    updateAuthStatus(true, data.user_email);
                    addLog('Qwen Code authentication successful');
                    if (authWindow && !authWindow.closed) authWindow.close();
                    fetchAndRenderModels(true);
                    break;
                case 'auth_failed':
                    updateAuthStatus(false, null, 'failed');
                    addLog('Authentication failed: ' + (data.error || 'Unknown error'));
                    break;
                case 'auth_logout':
                    updateAuthStatus(false);
                    addLog('Logged out from Qwen Code');
                    break;
            }
        }
        
        function updateStatus(status) {
            statusBadge.className = `status-badge status-${status}`;
            const statusLabels = {
                'pending': 'Pending Configuration',
                'configuring': 'Configuring...',
                'authenticating': 'Authenticating...',
                'running': 'Running Autonomously',
                'completed': 'Completed',
                'failed': 'Failed'
            };
            statusText.textContent = statusLabels[status] || status;
        }
        
        function updateAuthStatus(authenticated, email = null, status = null) {
            isAuthenticated = authenticated;
            
            if (authenticated) {
                authStatus.className = 'auth-status authenticated';
                authIcon.innerHTML = '&#128275;';
                authText.textContent = email ? `Logged in: ${email}` : 'Authenticated';
                loginBtn.classList.add('hidden');
                logoutBtn.classList.remove('hidden');
            } else if (status === 'authenticating') {
                authStatus.className = 'auth-status';
                authIcon.innerHTML = '&#8987;';
                authText.textContent = 'Authenticating...';
            } else {
                authStatus.className = 'auth-status not-authenticated';
                authIcon.innerHTML = '&#128274;';
                authText.textContent = 'Not Authenticated';
                loginBtn.classList.remove('hidden');
                logoutBtn.classList.add('hidden');
            }
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
                    <p style="font-size: 0.8125rem; color: var(--text-secondary);">${escapeHtml(finding.description || '')}</p>
                </div>
            `;
            
            if (findingsList.querySelector('p')) findingsList.innerHTML = '';
            findingsList.insertAdjacentHTML('afterbegin', html);
            
            const count = findingsList.querySelectorAll('.finding-item').length;
            findingsCount.textContent = `${count} found`;
        }
        
        function addLog(message) {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            const time = new Date().toLocaleTimeString();
            entry.textContent = `[${time}] ${message}`;
            logsContainer.appendChild(entry);
            logsContainer.scrollTop = logsContainer.scrollHeight;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Fetch and render available models
        async function fetchAndRenderModels(forceRefresh = false) {
            try {
                const url = forceRefresh ? '/api/models?refresh=true' : '/api/models';
                const response = await fetch(url);
                const data = await response.json();
                availableModels = data.qwencode || {};
                
                if (data.authenticated && !isAuthenticated) {
                    checkAuthStatus();
                }
                
                renderModelCards(data.authenticated);
            } catch (error) {
                console.error('Failed to fetch models:', error);
                modelCardsContainer.innerHTML = `
                    <div class="model-card" style="text-align: center; color: var(--accent-danger);">
                        <p>Failed to load models. <a href="#" onclick="fetchAndRenderModels(true); return false;">Retry</a></p>
                    </div>
                `;
            }
        }
        
        function renderModelCards(apiAuthenticated = false) {
            const models = Object.entries(availableModels);
            
            if (models.length === 0) {
                // Show default models
                availableModels = {
                    'qwen3-coder-plus': { name: 'qwen3-coder-plus', display_name: 'Qwen3 Coder Plus', description: 'High-performance coding model - 262K context', context_window: 262000, free: true, endpoint: 'dashscope' },
                    'qwen/qwen3-coder:free': { name: 'qwen/qwen3-coder:free', display_name: 'Qwen3 Coder (OpenRouter)', description: '1,000 free calls/day worldwide', context_window: 128000, free: true, endpoint: 'openrouter' },
                };
            }
            
            let html = '';
            let isFirst = true;
            
            for (const [modelId, model] of Object.entries(availableModels)) {
                const isSelected = isFirst || modelId === selectedModel;
                if (isFirst) { selectedModel = modelId; isFirst = false; }
                
                const displayName = model.display_name || model.name || modelId;
                const description = model.description || 'Qwen Code model';
                const contextWindow = model.context_window || 128000;
                const isFree = model.free !== false;
                const endpoint = model.endpoint || 'dashscope';
                const isIntl = endpoint === 'openrouter' || endpoint === 'dashscope_intl';
                
                html += `
                    <div class="model-card ${isSelected ? 'selected' : ''}" data-model="${escapeHtml(modelId)}">
                        <h3>&#129302; ${escapeHtml(displayName)}</h3>
                        <p>${escapeHtml(description)}</p>
                        <div class="model-meta">
                            ${isFree ? '<span class="model-tag free">FREE</span>' : '<span class="model-tag">PAID</span>'}
                            <span class="model-tag">${(contextWindow / 1000).toFixed(0)}K</span>
                            ${isIntl ? '<span class="model-tag intl">INTL</span>' : ''}
                        </div>
                    </div>
                `;
            }
            
            modelCardsContainer.innerHTML = html;
            
            // Re-attach click handlers
            document.querySelectorAll('.model-card').forEach(card => {
                card.addEventListener('click', () => {
                    document.querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
                    card.classList.add('selected');
                    selectedModel = card.dataset.model;
                    addLog(`Selected model: ${selectedModel}`);
                });
            });
        }
        
        // Refresh models button
        document.getElementById('refreshModelsBtn').addEventListener('click', () => {
            addLog('Refreshing available models...');
            fetchAndRenderModels(true);
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
        
        // Rate limit slider
        document.getElementById('rateLimit').addEventListener('input', (e) => {
            document.getElementById('rateLimitValue').textContent = e.target.value;
        });
        
        // Login button (Qwen OAuth)
        loginBtn.addEventListener('click', async () => {
            try {
                addLog('Initiating Qwen Code login...');
                const response = await fetch('/api/qwencode/login');
                const data = await response.json();
                
                if (data.auth_url) {
                    addLog('Opening qwen.ai login page...');
                    if (data.note) addLog(data.note);
                    
                    authWindow = window.open(data.auth_url, 'qwencode_auth', 'width=600,height=700');
                    
                    window.addEventListener('message', function authListener(event) {
                        if (event.data.type === 'qwencode_auth_success') {
                            updateAuthStatus(true);
                            addLog('Authentication successful');
                            window.removeEventListener('message', authListener);
                            checkAuthStatus();
                            fetchAndRenderModels(true);
                        } else if (event.data.type === 'qwencode_auth_failed') {
                            updateAuthStatus(false, null, 'failed');
                            addLog('Authentication failed: ' + event.data.error);
                            window.removeEventListener('message', authListener);
                        }
                    });
                    
                    // Poll for auth status
                    let pollCount = 0;
                    const pollInterval = setInterval(async () => {
                        pollCount++;
                        if (pollCount > 60 || isAuthenticated) { clearInterval(pollInterval); return; }
                        try {
                            const statusResp = await fetch('/api/qwencode/status');
                            const statusData = await statusResp.json();
                            if (statusData.authenticated && !isAuthenticated) {
                                updateAuthStatus(true, statusData.user_email);
                                addLog('Authentication successful');
                                fetchAndRenderModels(true);
                                clearInterval(pollInterval);
                                if (authWindow && !authWindow.closed) authWindow.close();
                            }
                        } catch (e) {}
                    }, 2000);
                }
            } catch (error) {
                addLog('Login error: ' + error.message);
            }
        });
        
        // Logout button
        logoutBtn.addEventListener('click', async () => {
            try {
                await fetch('/api/qwencode/logout', { method: 'POST' });
                updateAuthStatus(false);
                addLog('Logged out successfully');
            } catch (error) {
                addLog('Logout error: ' + error.message);
            }
        });
        
        // Set API Key button
        document.getElementById('setApiKeyBtn').addEventListener('click', async () => {
            const apiKey = document.getElementById('qwenApiKey').value.trim();
            const apiEndpoint = document.getElementById('qwenApiEndpoint').value.trim() || selectedEndpoint;
            
            if (!apiKey) {
                alert('Please enter an API key');
                return;
            }
            
            try {
                addLog(`Setting API key for ${selectedProvider}...`);
                const response = await fetch('/api/qwencode/set-token', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: apiKey,
                        api_endpoint: apiEndpoint,
                        api_provider: selectedProvider,
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    updateAuthStatus(true);
                    addLog(`API key set successfully (${data.api_provider})`);
                    document.getElementById('qwenApiKey').value = '';
                    fetchAndRenderModels(true);
                } else {
                    throw new Error(data.detail || 'Failed to set API key');
                }
            } catch (error) {
                addLog('Error: ' + error.message);
                alert('Error: ' + error.message);
            }
        });
        
        // Check auth status
        async function checkAuthStatus() {
            try {
                const response = await fetch('/api/qwencode/status');
                const data = await response.json();
                const wasAuthenticated = isAuthenticated;
                updateAuthStatus(data.authenticated, data.user_email);
                
                if (data.authenticated && !wasAuthenticated) {
                    addLog('Session restored');
                    await fetchAndRenderModels(true);
                }
            } catch (error) {
                console.error('Error checking auth status:', error);
            }
        }
        
        // Fire button
        fireBtn.addEventListener('click', async () => {
            const target = document.getElementById('target').value.trim();
            if (!target) {
                alert('Please enter a primary target');
                return;
            }
            
            if (!isAuthenticated) {
                alert('Please authenticate with Qwen Code first (use OAuth or enter API key)');
                return;
            }
            
            if (!confirm('Once started, the agent will run autonomously without interruption. Continue?')) {
                return;
            }
            
            fireBtn.disabled = true;
            fireBtn.textContent = 'Saving configuration...';
            
            try {
                const additionalTargets = document.getElementById('additionalTargets').value
                    .split('\\n').map(t => t.trim()).filter(t => t.length > 0);
                
                const config = {
                    target: target,
                    additional_targets: additionalTargets,
                    duration_minutes: parseInt(document.getElementById('duration').value),
                    max_iterations: parseInt(document.getElementById('maxIterations').value),
                    instructions: document.getElementById('instructions').value,
                    ai_provider: 'qwencode',
                    ai_model: selectedModel,
                    access_level: document.getElementById('accessLevel').value,
                    allow_package_install: document.getElementById('allowPackageInstall').checked,
                    allow_tool_download: document.getElementById('allowToolDownload').checked,
                    allow_network_config: document.getElementById('allowNetworkConfig').checked,
                    allow_system_modification: document.getElementById('allowSystemMod').checked,
                    command_timeout: parseInt(document.getElementById('commandTimeout').value),
                    focus_areas: selectedFocusAreas,
                    planning_depth: document.getElementById('planningDepth').value,
                    memory_strategy: document.getElementById('memoryStrategy').value,
                    enable_multi_agent: document.getElementById('enableMultiAgent').checked,
                    enable_browser_automation: document.getElementById('enableBrowser').checked,
                    enable_proxy_interception: document.getElementById('enableProxy').checked,
                    enable_web_search: document.getElementById('enableWebSearch').checked,
                    chain_attacks: document.getElementById('chainAttacks').checked,
                    auto_pivot: document.getElementById('autoPivot').checked,
                    rate_limit_rps: parseInt(document.getElementById('rateLimit').value),
                    output_format: document.getElementById('outputFormat').value,
                    severity_threshold: document.getElementById('severityThreshold').value,
                    save_artifacts: document.getElementById('saveArtifacts').checked,
                    include_screenshots: document.getElementById('includeScreenshots').checked,
                    include_poc: document.getElementById('includePoc').checked,
                    notification_webhook: document.getElementById('webhook').value || null,
                };
                
                const configResponse = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                if (!configResponse.ok) {
                    const error = await configResponse.json();
                    throw new Error(error.detail || 'Failed to save configuration');
                }
                
                addLog('Configuration saved');
                fireBtn.textContent = 'Starting scan...';
                
                const startResponse = await fetch('/api/start', { method: 'POST' });
                if (!startResponse.ok) {
                    const error = await startResponse.json();
                    throw new Error(error.detail || 'Failed to start scan');
                }
                
                addLog('Scan started successfully');
                
            } catch (error) {
                addLog('Error: ' + error.message);
                alert('Error: ' + error.message);
                fireBtn.disabled = false;
                fireBtn.innerHTML = '&#128293; CONFIGURE AND FIRE';
            }
        });
        
        // Initialize
        connectWebSocket();
        checkAuthStatus();
        fetchAndRenderModels();
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Strix Dashboard Server - Powered by Qwen Code")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    run_dashboard(host=args.host, port=args.port, debug=args.debug)
