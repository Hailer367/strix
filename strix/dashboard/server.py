#!/usr/bin/env python3
"""
Strix Dashboard Server

A FastAPI-based web server that provides a configuration dashboard for
autonomous bug bounty operations through GitHub Actions.

Features:
- Configure-and-Fire: Set all parameters before starting
- Roo Code OAuth: Browser-based authentication directly from dashboard
- Real-time WebSocket: Live updates on scan progress
- Advanced Agent Configuration: Fine-tune Strix agent behavior
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import (
    DEFAULT_FOCUS_AREAS,
    ROOCODE_MODELS,
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
    RooCodeConfig,
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

# Roo Code OAuth configuration
ROOCODE_AUTH_URL = "https://app.roocode.com"
ROOCODE_API_URL = "https://api.roocode.com"
ROOCODE_INFERENCE_URL = "https://api.roocode.com/v1"
ROOCODE_CONFIG_DIR = Path.home() / ".strix"
ROOCODE_CONFIG_FILE = ROOCODE_CONFIG_DIR / "roocode_config.json"

# Cache for dynamic models
_cached_roocode_models: dict[str, dict[str, Any]] | None = None
_models_cache_time: float = 0

# Global state
dashboard_config = DashboardConfig()
dashboard_state = DashboardState()
connected_websockets: list[WebSocket] = []


def generate_code_verifier() -> str:
    """Generate a code verifier for PKCE OAuth flow."""
    return secrets.token_urlsafe(32)


def generate_code_challenge(verifier: str) -> str:
    """Generate a code challenge from the verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()


def save_roocode_credentials(
    access_token: str,
    refresh_token: str | None = None,
    expires_at: float | None = None,
    user_email: str | None = None,
    user_id: str | None = None,
) -> None:
    """Save Roo Code credentials to config file."""
    try:
        ROOCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "user_email": user_email,
            "user_id": user_id,
        }
        with open(ROOCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        ROOCODE_CONFIG_FILE.chmod(0o600)
        logger.info("Saved Roo Code credentials to config")
    except OSError as e:
        logger.warning(f"Failed to save Roo Code credentials: {e}")


def load_roocode_credentials() -> dict[str, Any] | None:
    """Load Roo Code credentials from config file."""
    if ROOCODE_CONFIG_FILE.exists():
        try:
            with open(ROOCODE_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load Roo Code credentials: {e}")
    return None


async def fetch_roocode_models(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    """
    Fetch available models from Roo Code Cloud API.
    
    Models are ONLY fetched when the user is authenticated.
    No fallback to hardcoded models - we only show what the API provides.
    
    Args:
        force_refresh: Force refresh from API even if cache is valid
        
    Returns:
        Dictionary of available models, empty if not authenticated or API fails
    """
    global _cached_roocode_models, _models_cache_time
    
    # Return empty if not authenticated - models require login
    if dashboard_state.auth_status != AuthStatus.AUTHENTICATED or not dashboard_state.roocode_access_token:
        logger.debug("Not authenticated, returning empty models list")
        return {}
    
    # Use cached models if available and not expired (cache for 30 minutes)
    cache_ttl = 1800  # 30 minutes - shorter cache for fresher data
    if (
        not force_refresh
        and _cached_roocode_models
        and (time.time() - _models_cache_time) < cache_ttl
    ):
        return _cached_roocode_models

    # Fetch models from API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ROOCODE_API_URL}/v1/models",
                headers={"Authorization": f"Bearer {dashboard_state.roocode_access_token}"},
                timeout=30,
            )
            
            if response.status_code == 401:
                # Token expired or invalid
                logger.warning("Roo Code token appears invalid, clearing auth state")
                dashboard_state.auth_status = AuthStatus.EXPIRED
                return {}
            
            if response.status_code == 200:
                data = response.json()
                models = {}
                
                # Handle both OpenAI-style response (data array) and direct array
                model_list = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                
                for model in model_list:
                    model_id = model.get("id", "")
                    if model_id:
                        # Parse model metadata
                        pricing = model.get("pricing", {})
                        is_free = pricing.get("free", False) if isinstance(pricing, dict) else False
                        
                        models[model_id] = {
                            "name": model_id,
                            "display_name": model.get("name", model_id),
                            "description": model.get("description", "AI model from Roo Code Cloud"),
                            "context_window": model.get("context_length", model.get("context_window", 128000)),
                            "free": is_free,
                            "provider": model.get("provider", "roocode"),
                            "capabilities": model.get("capabilities", ["code", "chat"]),
                            "speed": model.get("speed", "moderate"),
                            "cost": "free" if is_free else "paid",
                        }
                
                if models:
                    _cached_roocode_models = models
                    _models_cache_time = time.time()
                    logger.info(f"Fetched {len(models)} models from Roo Code Cloud API")
                    return models
                else:
                    logger.warning("API returned empty model list")
                    return {}
            else:
                logger.warning(f"Failed to fetch models: HTTP {response.status_code}")
                # Return cached models if available, otherwise empty
                return _cached_roocode_models if _cached_roocode_models else {}
                
    except httpx.TimeoutException:
        logger.warning("Timeout fetching models from Roo Code API")
        return _cached_roocode_models if _cached_roocode_models else {}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to fetch models from API: {e}")
        return _cached_roocode_models if _cached_roocode_models else {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    logger.info("Strix Dashboard starting up...")
    
    # Check for existing Roo Code credentials
    creds = load_roocode_credentials()
    if creds and creds.get("access_token"):
        expires_at = creds.get("expires_at", 0)
        if expires_at == 0 or time.time() < expires_at:
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            dashboard_state.roocode_access_token = creds["access_token"]
            dashboard_state.roocode_refresh_token = creds.get("refresh_token")
            dashboard_state.roocode_user_email = creds.get("user_email")
            dashboard_state.roocode_user_id = creds.get("user_id")
            dashboard_state.roocode_token_expires_at = expires_at
            logger.info("Loaded existing Roo Code credentials")
    
    # Check for environment token
    env_token = os.getenv("ROOCODE_ACCESS_TOKEN")
    if env_token and dashboard_state.auth_status != AuthStatus.AUTHENTICATED:
        dashboard_state.auth_status = AuthStatus.AUTHENTICATED
        dashboard_state.roocode_access_token = env_token
        # Save to config file for persistence
        save_roocode_credentials(env_token, expires_at=time.time() + 3600 * 24 * 365)
        logger.info("Using Roo Code token from environment")
    
    yield
    
    logger.info("Strix Dashboard shutting down...")
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
        version="2.0.0",
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
            "user_email": dashboard_state.roocode_user_email,
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
            
            ai_provider = AIProvider(data.get("ai_provider", "roocode"))
            roocode_config = RooCodeConfig(
                enabled=ai_provider == AIProvider.ROOCODE,
                model=data.get("ai_model", "grok-code-fast-1"),
                access_token=dashboard_state.roocode_access_token,
                refresh_token=dashboard_state.roocode_refresh_token,
                expires_at=dashboard_state.roocode_token_expires_at,
                user_email=dashboard_state.roocode_user_email,
                user_id=dashboard_state.roocode_user_id,
                auth_status=dashboard_state.auth_status,
            )
            
            ai_config = AIConfig(
                provider=ai_provider,
                model=data.get("ai_model", "grok-code-fast-1"),
                api_key=data.get("api_key"),
                api_base=data.get("api_base"),
                roocode=roocode_config,
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
        
        # Verify authentication for Roo Code
        if dashboard_state.config.ai.provider == AIProvider.ROOCODE:
            if dashboard_state.auth_status != AuthStatus.AUTHENTICATED:
                raise HTTPException(
                    status_code=401,
                    detail="Please authenticate with Roo Code first"
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
        """Get available AI models and configuration options.
        
        Models are only fetched from the API if the user is authenticated.
        When not authenticated, returns an empty model list to indicate
        that login is required.
        
        Args:
            refresh: Force refresh models from API (ignoring cache)
        """
        # Only fetch models if authenticated
        if dashboard_state.auth_status == AuthStatus.AUTHENTICATED:
            roocode_models = await fetch_roocode_models(force_refresh=refresh)
        else:
            # Return empty models when not authenticated
            # This signals to the frontend that login is required
            roocode_models = {}
        
        return {
            "roocode": roocode_models,
            "authenticated": dashboard_state.auth_status == AuthStatus.AUTHENTICATED,
            "auth_status": dashboard_state.auth_status.value,
            "focus_areas": DEFAULT_FOCUS_AREAS,
            "planning_depths": PLANNING_DEPTHS,
            "memory_strategies": MEMORY_STRATEGIES,
            "severity_levels": SEVERITY_LEVELS,
            "output_formats": OUTPUT_FORMATS,
        }
    
    # =========================================================================
    # Roo Code OAuth Routes
    # =========================================================================
    
    @app.get("/api/roocode/status")
    async def roocode_status() -> dict[str, Any]:
        """Get Roo Code authentication status."""
        return {
            "authenticated": dashboard_state.auth_status == AuthStatus.AUTHENTICATED,
            "status": dashboard_state.auth_status.value,
            "user_email": dashboard_state.roocode_user_email,
            "user_id": dashboard_state.roocode_user_id,
            "expires_at": dashboard_state.roocode_token_expires_at,
        }
    
    @app.get("/api/roocode/login")
    async def roocode_login_redirect(request: Request) -> dict[str, Any]:
        """Get the Roo Code OAuth login URL."""
        # Generate state for security
        state = secrets.token_urlsafe(16)
        
        # Store for callback verification
        dashboard_state.oauth_state = state
        dashboard_state.auth_status = AuthStatus.AUTHENTICATING
        
        # Build callback URL - use the dashboard's own callback endpoint
        host = request.headers.get("host", f"localhost:{dashboard_config.port}")
        scheme = request.headers.get("x-forwarded-proto", "http")
        callback_url = f"{scheme}://{host}/api/roocode/callback"
        
        # Use the Roo Code Cloud sign-in page with redirect
        # This is the official authentication flow for external tools
        # Reference: https://docs.roocode.com/roo-code-cloud/login
        auth_url = f"{ROOCODE_AUTH_URL}/sign-in?redirect_uri={callback_url}&state={state}&app=strix"
        
        # Alternative: Direct sign-up URL for new users
        signup_url = f"{ROOCODE_AUTH_URL}/sign-up?redirect_uri={callback_url}&state={state}&app=strix"
        
        await broadcast_update({
            "type": "auth_started",
            "status": "authenticating",
        })
        
        return {
            "auth_url": auth_url,
            "signup_url": signup_url,
            "state": state,
            "callback_url": callback_url,
            "instructions": "Sign in with your Roo Code Cloud account (GitHub, Google, or email)",
        }
    
    @app.get("/api/roocode/callback", response_model=None)
    async def roocode_callback(
        request: Request,
        token: str | None = None,
        access_token: str | None = None,
        session_token: str | None = None,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
        error_description: str | None = None,
    ) -> HTMLResponse | RedirectResponse:
        """Handle Roo Code OAuth callback.
        
        This handles the OAuth redirect from Roo Code Cloud authentication.
        After successful authentication, it redirects back to the dashboard
        with the auth state properly set.
        """
        
        if error:
            error_msg = error_description or error
            dashboard_state.auth_status = AuthStatus.FAILED
            await broadcast_update({
                "type": "auth_failed",
                "error": error_msg,
            })
            return HTMLResponse(content=get_auth_result_html(False, error_msg), status_code=400)
        
        # Handle direct token (multiple possible parameter names)
        received_token = token or access_token or session_token
        if received_token:
            dashboard_state.roocode_access_token = received_token
            dashboard_state.roocode_token_expires_at = time.time() + 3600 * 24 * 30  # 30 days
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            
            # Try to fetch user info with the token
            try:
                async with httpx.AsyncClient() as client:
                    user_response = await client.get(
                        f"{ROOCODE_API_URL}/v1/user",
                        headers={"Authorization": f"Bearer {received_token}"},
                        timeout=30,
                    )
                    if user_response.status_code == 200:
                        user_data = user_response.json()
                        dashboard_state.roocode_user_email = user_data.get("email")
                        dashboard_state.roocode_user_id = user_data.get("id")
            except Exception:  # noqa: BLE001
                pass
            
            # Save credentials
            save_roocode_credentials(
                access_token=received_token,
                expires_at=dashboard_state.roocode_token_expires_at,
                user_email=dashboard_state.roocode_user_email,
                user_id=dashboard_state.roocode_user_id,
            )
            
            # Set environment variable for the agent
            os.environ["ROOCODE_ACCESS_TOKEN"] = received_token
            
            # Clear any cached models to force refresh with new token
            global _cached_roocode_models, _models_cache_time
            _cached_roocode_models = None
            _models_cache_time = 0
            
            await broadcast_update({
                "type": "auth_success",
                "user_email": dashboard_state.roocode_user_email,
            })
            
            # Return success page that will redirect to dashboard or close popup
            return HTMLResponse(content=get_auth_result_html(True), status_code=200)
        
        # Handle OAuth authorization code exchange
        if code:
            # Optionally verify state for security
            if state and dashboard_state.oauth_state and state != dashboard_state.oauth_state:
                logger.warning("OAuth state mismatch, but continuing...")
            
            try:
                # Exchange code for token
                host = request.headers.get("host", f"localhost:{dashboard_config.port}")
                scheme = request.headers.get("x-forwarded-proto", "http")
                callback_url = f"{scheme}://{host}/api/roocode/callback"
                
                async with httpx.AsyncClient() as client:
                    # Try multiple token exchange endpoints
                    token_data = None
                    for token_endpoint in [
                        f"{ROOCODE_API_URL}/v1/auth/token",
                        f"{ROOCODE_API_URL}/oauth/token",
                        f"{ROOCODE_API_URL}/v1/oauth/token",
                    ]:
                        try:
                            response = await client.post(
                                token_endpoint,
                                data={
                                    "grant_type": "authorization_code",
                                    "code": code,
                                    "redirect_uri": callback_url,
                                },
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                timeout=30,
                            )
                            if response.status_code == 200:
                                token_data = response.json()
                                break
                        except Exception:  # noqa: BLE001
                            continue
                    
                    if not token_data:
                        raise ValueError("Failed to exchange authorization code for token")
                
                received_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 3600 * 24)
                
                if not received_token:
                    raise ValueError("No access_token in response")
                
                dashboard_state.roocode_access_token = received_token
                dashboard_state.roocode_refresh_token = refresh_token
                dashboard_state.roocode_token_expires_at = time.time() + expires_in
                dashboard_state.auth_status = AuthStatus.AUTHENTICATED
                
                # Try to get user info
                try:
                    async with httpx.AsyncClient() as client:
                        user_response = await client.get(
                            f"{ROOCODE_API_URL}/v1/user",
                            headers={"Authorization": f"Bearer {received_token}"},
                            timeout=30,
                        )
                        if user_response.status_code == 200:
                            user_data = user_response.json()
                            dashboard_state.roocode_user_email = user_data.get("email")
                            dashboard_state.roocode_user_id = user_data.get("id")
                except Exception:  # noqa: BLE001
                    pass
                
                # Save credentials
                save_roocode_credentials(
                    access_token=received_token,
                    refresh_token=refresh_token,
                    expires_at=dashboard_state.roocode_token_expires_at,
                    user_email=dashboard_state.roocode_user_email,
                    user_id=dashboard_state.roocode_user_id,
                )
                
                # Set environment variable
                os.environ["ROOCODE_ACCESS_TOKEN"] = received_token
                
                # Clear any cached models to force refresh with new token
                _cached_roocode_models = None
                _models_cache_time = 0
                
                await broadcast_update({
                    "type": "auth_success",
                    "user_email": dashboard_state.roocode_user_email,
                })
                
                return HTMLResponse(content=get_auth_result_html(True), status_code=200)
                
            except Exception as e:
                logger.error(f"Token exchange failed: {e}")
                dashboard_state.auth_status = AuthStatus.FAILED
                await broadcast_update({
                    "type": "auth_failed",
                    "error": str(e),
                })
                return HTMLResponse(
                    content=get_auth_result_html(False, str(e)),
                    status_code=500
                )
        
        return HTMLResponse(
            content=get_auth_result_html(False, "No token or code received"),
            status_code=400
        )
    
    @app.post("/api/roocode/logout")
    async def roocode_logout() -> dict[str, Any]:
        """Log out from Roo Code."""
        dashboard_state.auth_status = AuthStatus.NOT_AUTHENTICATED
        dashboard_state.roocode_access_token = None
        dashboard_state.roocode_refresh_token = None
        dashboard_state.roocode_user_email = None
        dashboard_state.roocode_user_id = None
        dashboard_state.roocode_token_expires_at = None
        
        # Remove environment variable
        if "ROOCODE_ACCESS_TOKEN" in os.environ:
            del os.environ["ROOCODE_ACCESS_TOKEN"]
        
        # Remove saved credentials
        if ROOCODE_CONFIG_FILE.exists():
            try:
                ROOCODE_CONFIG_FILE.unlink()
            except OSError:
                pass
        
        await broadcast_update({
            "type": "auth_logout",
        })
        
        return {"success": True, "message": "Logged out successfully"}
    
    @app.post("/api/roocode/set-token")
    async def roocode_set_token(request: Request) -> dict[str, Any]:
        """Manually set Roo Code access token."""
        try:
            data = await request.json()
            token = data.get("token")
            
            if not token:
                raise HTTPException(status_code=400, detail="Token is required")
            
            dashboard_state.roocode_access_token = token
            dashboard_state.roocode_token_expires_at = time.time() + 3600 * 24 * 365
            dashboard_state.auth_status = AuthStatus.AUTHENTICATED
            
            # Save credentials
            save_roocode_credentials(
                access_token=token,
                expires_at=dashboard_state.roocode_token_expires_at,
            )
            
            # Set environment variable
            os.environ["ROOCODE_ACCESS_TOKEN"] = token
            
            await broadcast_update({
                "type": "auth_success",
                "user_email": None,
            })
            
            return {"success": True, "message": "Token set successfully"}
            
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
                "user_email": dashboard_state.roocode_user_email,
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


def generate_env_config(config: ScanConfig) -> str:
    """Generate environment variables configuration."""
    lines = [
        "# Strix Dashboard Generated Configuration",
        f"# Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "# AI Configuration",
    ]
    
    if config.ai.provider == AIProvider.ROOCODE:
        lines.extend([
            "STRIX_USE_ROOCODE=true",
            f"STRIX_LLM=roocode/{config.ai.model}",
        ])
        if config.ai.roocode.access_token:
            lines.append(f"ROOCODE_ACCESS_TOKEN={config.ai.roocode.access_token}")
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
    if config.ai.provider == AIProvider.ROOCODE:
        os.environ["STRIX_USE_ROOCODE"] = "true"
        os.environ["STRIX_LLM"] = f"roocode/{config.ai.model}"
        if config.ai.roocode.access_token:
            os.environ["ROOCODE_ACCESS_TOKEN"] = config.ai.roocode.access_token
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
    """Generate HTML page for auth callback result.
    
    This page handles both popup window and full page redirect scenarios.
    It attempts to notify the parent/opener window and auto-close if opened as popup,
    otherwise provides a manual redirect link to the dashboard.
    """
    if success:
        return '''<!DOCTYPE html>
<html>
<head>
    <title>Strix - Authentication Successful</title>
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
        .redirect-info { color: #94a3b8; font-size: 0.875rem; margin-top: 20px; }
        .redirect-link { color: #22c55e; text-decoration: underline; cursor: pointer; }
    </style>
    <script>
        // Notify parent window and handle redirect
        (function() {
            let handled = false;
            
            // Try to notify opener window (popup scenario)
            if (window.opener) {
                try {
                    window.opener.postMessage({ type: 'roocode_auth_success' }, '*');
                    handled = true;
                    // Auto-close popup after short delay
                    setTimeout(() => {
                        window.close();
                    }, 1500);
                } catch (e) {
                    console.log('Could not communicate with opener:', e);
                }
            }
            
            // If not a popup, redirect to dashboard after delay
            if (!handled && !window.opener) {
                document.getElementById('redirect-info').style.display = 'block';
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
            }
        })();
        
        function goToDashboard() {
            window.location.href = '/';
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="icon">🦉</div>
        <h1>Authentication Successful!</h1>
        <p class="success">✓ Connected to Roo Code Cloud</p>
        <p>You are now authenticated and can use Roo Code Cloud models.</p>
        <button class="btn" onclick="goToDashboard()">Go to Dashboard</button>
        <p id="redirect-info" class="redirect-info" style="display: none;">
            Redirecting to dashboard... <span class="redirect-link" onclick="goToDashboard()">Click here</span> if not redirected.
        </p>
    </div>
</body>
</html>'''
    else:
        return f'''<!DOCTYPE html>
<html>
<head>
    <title>Strix - Authentication Failed</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center; height: 100vh;
               margin: 0; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }}
        .container {{ text-align: center; padding: 40px; background: rgba(255,255,255,0.1);
                     border-radius: 16px; backdrop-filter: blur(10px); max-width: 400px; }}
        h1 {{ color: #ef4444; margin-bottom: 16px; }}
        p {{ color: #e5e5e5; margin: 10px 0; }}
        .icon {{ font-size: 64px; margin-bottom: 20px; }}
        .error {{ color: #fca5a5; background: rgba(239, 68, 68, 0.2);
                 padding: 10px 15px; border-radius: 8px; margin: 15px 0; word-break: break-word; }}
        .btn {{ display: inline-block; margin-top: 20px; padding: 12px 24px;
               background: #3b82f6; color: #fff; text-decoration: none;
               border-radius: 8px; font-weight: 600; cursor: pointer; }}
        .btn:hover {{ background: #2563eb; }}
        .btn-secondary {{ background: #475569; margin-left: 10px; }}
        .btn-secondary:hover {{ background: #64748b; }}
    </style>
    <script>
        // Notify parent window
        if (window.opener) {{
            try {{
                window.opener.postMessage({{ type: 'roocode_auth_failed', error: '{error or "Unknown error"}' }}, '*');
            }} catch (e) {{
                console.log('Could not communicate with opener:', e);
            }}
        }}
        
        function tryAgain() {{
            if (window.opener) {{
                window.close();
            }} else {{
                window.location.href = '/';
            }}
        }}
        
        function goToDashboard() {{
            window.location.href = '/';
        }}
    </script>
</head>
<body>
    <div class="container">
        <div class="icon">❌</div>
        <h1>Authentication Failed</h1>
        <p class="error">{error or "Unknown error occurred"}</p>
        <p>Please try again or contact support if the issue persists.</p>
        <button class="btn" onclick="tryAgain()">Try Again</button>
        <button class="btn btn-secondary" onclick="goToDashboard()">Go to Dashboard</button>
    </div>
</body>
</html>'''


def get_dashboard_html() -> str:
    """Generate the dashboard HTML with enhanced configuration options."""
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
            --accent-purple: #8b5cf6;
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
            max-width: 1600px;
            margin: 0 auto;
            padding: 1.5rem;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 2rem;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 1rem;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .logo-icon {
            font-size: 2rem;
        }
        
        .logo-text h1 {
            font-size: 1.25rem;
            color: var(--accent-primary);
        }
        
        .logo-text p {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }
        
        .header-status {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .auth-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: var(--bg-tertiary);
            border-radius: 8px;
            font-size: 0.875rem;
        }
        
        .auth-status.authenticated {
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid var(--accent-primary);
        }
        
        .auth-status.not-authenticated {
            background: rgba(245, 158, 11, 0.2);
            border: 1px solid var(--accent-warning);
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
        .status-authenticating { background: var(--accent-purple); }
        .status-running { background: var(--accent-primary); color: #000; }
        .status-completed { background: var(--accent-primary); color: #000; }
        .status-failed { background: var(--accent-danger); }
        
        .main-content {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
            margin-top: 1.5rem;
        }
        
        @media (max-width: 1200px) {
            .main-content {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background: var(--bg-secondary);
            border-radius: 1rem;
            border: 1px solid var(--border-color);
            overflow: hidden;
        }
        
        .card-header {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-header h2 {
            font-size: 1rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .card-body {
            padding: 1.25rem;
        }
        
        .form-group {
            margin-bottom: 1.25rem;
        }
        
        .form-group:last-child {
            margin-bottom: 0;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-size: 0.8125rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 0.625rem 0.875rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            color: var(--text-primary);
            font-size: 0.875rem;
        }
        
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: var(--accent-primary);
        }
        
        .form-group textarea {
            min-height: 80px;
            resize: vertical;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
        }
        
        .checkbox-group input[type="checkbox"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
        }
        
        .checkbox-group label {
            margin: 0;
            cursor: pointer;
            font-size: 0.8125rem;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.625rem 1.25rem;
            border-radius: 0.5rem;
            font-size: 0.875rem;
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
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: var(--border-color);
        }
        
        .btn-danger {
            background: var(--accent-danger);
            color: #fff;
        }
        
        .btn-warning {
            background: var(--accent-warning);
            color: #000;
        }
        
        .btn-large {
            padding: 0.875rem 1.75rem;
            font-size: 1rem;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .btn-block {
            width: 100%;
        }
        
        .fire-btn {
            width: 100%;
            margin-top: 1rem;
            background: linear-gradient(135deg, var(--accent-danger), var(--accent-warning));
            font-size: 1.125rem;
            padding: 1rem;
        }
        
        .fire-btn:hover:not(:disabled) {
            transform: scale(1.02);
        }
        
        .model-cards {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }
        
        .model-card {
            padding: 0.875rem;
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
        
        .model-card .model-meta {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        
        .model-tag {
            font-size: 0.625rem;
            padding: 0.125rem 0.375rem;
            background: var(--bg-primary);
            border-radius: 4px;
            color: var(--text-secondary);
        }
        
        .model-tag.free {
            background: rgba(34, 197, 94, 0.2);
            color: var(--accent-primary);
        }
        
        .focus-areas {
            display: flex;
            flex-wrap: wrap;
            gap: 0.375rem;
        }
        
        .focus-tag {
            padding: 0.25rem 0.625rem;
            background: var(--bg-tertiary);
            border-radius: 9999px;
            font-size: 0.6875rem;
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
            max-height: 350px;
            overflow-y: auto;
        }
        
        .finding-item {
            padding: 0.875rem;
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
            font-size: 0.875rem;
        }
        
        .severity-badge {
            padding: 0.125rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.6875rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .severity-critical { background: #dc2626; }
        .severity-high { background: #ea580c; }
        .severity-medium { background: #d97706; }
        .severity-low { background: #2563eb; }
        .severity-info { background: #6b7280; }
        
        .progress-bar {
            height: 6px;
            background: var(--bg-tertiary);
            border-radius: 9999px;
            overflow: hidden;
            margin-bottom: 0.75rem;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            transition: width 0.3s;
        }
        
        .logs-container {
            background: var(--bg-primary);
            border-radius: 0.5rem;
            padding: 0.75rem;
            max-height: 250px;
            overflow-y: auto;
            font-family: 'Fira Code', 'Monaco', monospace;
            font-size: 0.75rem;
        }
        
        .log-entry {
            padding: 0.25rem 0;
            color: var(--text-secondary);
            word-break: break-all;
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        .col-span-2 {
            grid-column: span 2;
        }
        
        .warning-notice {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            padding: 0.875rem;
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid var(--accent-warning);
            border-radius: 0.5rem;
            margin-bottom: 1.25rem;
        }
        
        .warning-notice p {
            font-size: 0.8125rem;
            color: var(--accent-warning);
        }
        
        .info-notice {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            padding: 0.875rem;
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid var(--accent-secondary);
            border-radius: 0.5rem;
            margin-bottom: 1.25rem;
        }
        
        .info-notice p {
            font-size: 0.8125rem;
            color: var(--accent-secondary);
        }
        
        .section-divider {
            height: 1px;
            background: var(--border-color);
            margin: 1.25rem 0;
        }
        
        .section-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.75rem;
        }
        
        .slider-container {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .slider-container input[type="range"] {
            flex: 1;
            -webkit-appearance: none;
            height: 6px;
            background: var(--bg-tertiary);
            border-radius: 3px;
        }
        
        .slider-container input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            background: var(--accent-primary);
            border-radius: 50%;
            cursor: pointer;
        }
        
        .slider-value {
            min-width: 40px;
            text-align: right;
            font-size: 0.875rem;
            color: var(--accent-primary);
        }
        
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 1rem;
        }
        
        .tab {
            padding: 0.75rem 1rem;
            cursor: pointer;
            font-size: 0.8125rem;
            color: var(--text-secondary);
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }
        
        .tab:hover {
            color: var(--text-primary);
        }
        
        .tab.active {
            color: var(--accent-primary);
            border-bottom-color: var(--accent-primary);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .hidden {
            display: none !important;
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
                    <h2>&#129302; AI Provider & Authentication</h2>
                </div>
                <div class="card-body">
                    <div class="info-notice" id="roocodeInfo">
                        <span>&#128161;</span>
                        <p><strong>Roo Code Cloud</strong> provides free AI models. Login with your Roo Code account to get started - no API keys needed!</p>
                    </div>
                    
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="aiProvider">
                            <option value="roocode" selected>Roo Code Cloud (Free)</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="custom">Custom API</option>
                        </select>
                    </div>
                    
                    <div id="roocodeAuth">
                        <button class="btn btn-primary btn-block" id="loginBtn">
                            &#128274; Login with Roo Code
                        </button>
                        <button class="btn btn-danger btn-block hidden" id="logoutBtn">
                            &#128275; Logout
                        </button>
                        
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
                    
                    <div id="customApiAuth" class="hidden">
                        <div class="form-group">
                            <label>API Key</label>
                            <input type="password" id="apiKey" placeholder="sk-...">
                        </div>
                        <div class="form-group">
                            <label>API Base URL (optional)</label>
                            <input type="text" id="apiBase" placeholder="https://api.openai.com/v1">
                        </div>
                        <div class="form-group">
                            <label>Model Name</label>
                            <input type="text" id="customModel" placeholder="gpt-4o">
                        </div>
                    </div>
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
                    
                    <div class="section-divider"></div>
                    
                    <div class="section-title">Testing Modes</div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="aggressiveMode">
                        <label for="aggressiveMode">Aggressive mode (faster, more noise)</label>
                    </div>
                    <div class="checkbox-group">
                        <input type="checkbox" id="stealthMode">
                        <label for="stealthMode">Stealth mode (slower, less detection)</label>
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
                        <span class="focus-tag" data-focus="info_disclosure">Info Disclosure</span>
                        <span class="focus-tag" data-focus="broken_access">Broken Access</span>
                        <span class="focus-tag" data-focus="api_security">API Security</span>
                        <span class="focus-tag" data-focus="crypto_failures">Crypto Failures</span>
                        <span class="focus-tag" data-focus="misconfig">Misconfig</span>
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
                    <div class="checkbox-group">
                        <input type="checkbox" id="exportSarif">
                        <label for="exportSarif">Export SARIF (IDE integration)</label>
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
                    
                    <button class="btn btn-primary btn-large fire-btn" id="fireBtn">
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
        let selectedModel = 'grok-code-fast-1';
        let selectedFocusAreas = [];
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
                    if (data.auth_status) {
                        updateAuthStatus(data.auth_status === 'authenticated', data.user_email);
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
                case 'auth_started':
                    updateAuthStatus(false, null, 'authenticating');
                    break;
                case 'auth_success':
                    updateAuthStatus(true, data.user_email);
                    addLog('Roo Code authentication successful');
                    if (authWindow && !authWindow.closed) {
                        authWindow.close();
                    }
                    break;
                case 'auth_failed':
                    updateAuthStatus(false, null, 'failed');
                    addLog('Authentication failed: ' + (data.error || 'Unknown error'));
                    break;
                case 'auth_logout':
                    updateAuthStatus(false);
                    addLog('Logged out from Roo Code');
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
                availableModels = data.roocode || {};
                const apiAuthenticated = data.authenticated || false;
                
                // Update local auth state from API response
                if (apiAuthenticated && !isAuthenticated) {
                    // API says we're authenticated but local state doesn't know
                    // This can happen after redirect-based login
                    checkAuthStatus();
                }
                
                renderModelCards(apiAuthenticated);
                
                if (forceRefresh && apiAuthenticated) {
                    const modelCount = Object.keys(availableModels).length;
                    addLog(`Refreshed models: ${modelCount} model(s) available`);
                }
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
            
            // Show login required message if not authenticated
            if (!isAuthenticated && !apiAuthenticated) {
                modelCardsContainer.innerHTML = `
                    <div class="model-card" style="text-align: center; padding: 2rem;">
                        <div style="font-size: 2rem; margin-bottom: 1rem;">&#128274;</div>
                        <p style="color: var(--accent-warning); font-weight: 500; margin-bottom: 0.5rem;">Login Required</p>
                        <p style="color: var(--text-secondary); font-size: 0.8125rem;">Please login with your Roo Code Cloud account to access AI models.</p>
                    </div>
                `;
                selectedModel = null;
                return;
            }
            
            if (models.length === 0) {
                modelCardsContainer.innerHTML = `
                    <div class="model-card" style="text-align: center; color: var(--text-secondary);">
                        <p>No models available from Roo Code Cloud. Click refresh to try again.</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            let isFirst = true;
            
            for (const [modelId, model] of models) {
                const isSelected = isFirst || modelId === selectedModel;
                if (isFirst) {
                    selectedModel = modelId;
                    isFirst = false;
                }
                
                const displayName = model.display_name || model.name || modelId;
                const description = model.description || 'AI model for code generation';
                const contextWindow = model.context_window || 128000;
                const isFree = model.free || model.cost === 'free';
                const speed = model.speed || 'moderate';
                
                // Choose icon based on model name
                let icon = '&#129302;';  // robot
                if (modelId.includes('grok') || modelId.includes('fast')) {
                    icon = '&#9889;';  // lightning
                } else if (modelId.includes('supernova') || modelId.includes('advanced')) {
                    icon = '&#11088;';  // star
                } else if (modelId.includes('claude')) {
                    icon = '&#129516;';  // brain
                } else if (modelId.includes('gpt')) {
                    icon = '&#128161;';  // lightbulb
                }
                
                html += `
                    <div class="model-card ${isSelected ? 'selected' : ''}" data-model="${escapeHtml(modelId)}">
                        <h3>${icon} ${escapeHtml(displayName)}</h3>
                        <p>${escapeHtml(description)}</p>
                        <div class="model-meta">
                            ${isFree ? '<span class="model-tag free">FREE</span>' : '<span class="model-tag">PAID</span>'}
                            <span class="model-tag">${(contextWindow / 1000).toFixed(0)}K</span>
                            <span class="model-tag">${escapeHtml(speed.toUpperCase())}</span>
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
            if (!isAuthenticated) {
                addLog('Please login first to refresh models');
                return;
            }
            addLog('Refreshing available models from Roo Code Cloud...');
            fetchAndRenderModels(true);  // Force refresh from API
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
            const roocodeAuth = document.getElementById('roocodeAuth');
            const customApiAuth = document.getElementById('customApiAuth');
            const roocodeInfo = document.getElementById('roocodeInfo');
            
            if (e.target.value === 'roocode') {
                roocodeAuth.classList.remove('hidden');
                customApiAuth.classList.add('hidden');
                roocodeInfo.classList.remove('hidden');
            } else {
                roocodeAuth.classList.add('hidden');
                customApiAuth.classList.remove('hidden');
                roocodeInfo.classList.add('hidden');
            }
        });
        
        // Rate limit slider
        document.getElementById('rateLimit').addEventListener('input', (e) => {
            document.getElementById('rateLimitValue').textContent = e.target.value;
        });
        
        // Login button
        loginBtn.addEventListener('click', async () => {
            try {
                addLog('Initiating Roo Code login...');
                const response = await fetch('/api/roocode/login');
                const data = await response.json();
                
                if (data.auth_url) {
                    addLog('Opening Roo Code Cloud login...');
                    if (data.instructions) {
                        addLog(data.instructions);
                    }
                    
                    // Open auth URL in new window
                    authWindow = window.open(data.auth_url, 'roocode_auth', 'width=600,height=700');
                    
                    // Listen for auth result message
                    window.addEventListener('message', function authListener(event) {
                        if (event.data.type === 'roocode_auth_success') {
                            updateAuthStatus(true);
                            addLog('Authentication successful');
                            window.removeEventListener('message', authListener);
                            // Refresh auth status and models
                            checkAuthStatus();
                            fetchAndRenderModels();
                        } else if (event.data.type === 'roocode_auth_failed') {
                            updateAuthStatus(false, null, 'failed');
                            addLog('Authentication failed: ' + event.data.error);
                            window.removeEventListener('message', authListener);
                        }
                    });
                    
                    // Also poll for auth status in case postMessage doesn't work
                    let pollCount = 0;
                    const maxPolls = 60;  // 2 minutes max
                    const pollInterval = setInterval(async () => {
                        pollCount++;
                        if (pollCount > maxPolls || isAuthenticated) {
                            clearInterval(pollInterval);
                            return;
                        }
                        try {
                            const statusResp = await fetch('/api/roocode/status');
                            const statusData = await statusResp.json();
                            if (statusData.authenticated && !isAuthenticated) {
                                updateAuthStatus(true, statusData.user_email);
                                addLog('Authentication successful (via polling)');
                                fetchAndRenderModels(true);  // Force refresh after login
                                clearInterval(pollInterval);
                                if (authWindow && !authWindow.closed) {
                                    authWindow.close();
                                }
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
                await fetch('/api/roocode/logout', { method: 'POST' });
                updateAuthStatus(false);
                availableModels = {};  // Clear models on logout
                renderModelCards(false);  // Re-render to show login required
                addLog('Logged out successfully');
            } catch (error) {
                addLog('Logout error: ' + error.message);
            }
        });
        
        // Check auth status and sync UI state
        async function checkAuthStatus() {
            try {
                const response = await fetch('/api/roocode/status');
                const data = await response.json();
                const wasAuthenticated = isAuthenticated;
                updateAuthStatus(data.authenticated, data.user_email);
                
                // If auth state changed to authenticated, refresh models
                if (data.authenticated && !wasAuthenticated) {
                    addLog('Session restored - fetching available models...');
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
            
            const provider = document.getElementById('aiProvider').value;
            if (provider === 'roocode' && !isAuthenticated) {
                alert('Please login with Roo Code first');
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
                
                // Build configuration
                const config = {
                    target: target,
                    additional_targets: additionalTargets,
                    duration_minutes: parseInt(document.getElementById('duration').value),
                    max_iterations: parseInt(document.getElementById('maxIterations').value),
                    instructions: document.getElementById('instructions').value,
                    ai_provider: provider,
                    ai_model: provider === 'roocode' ? selectedModel : document.getElementById('customModel').value,
                    api_key: document.getElementById('apiKey').value || null,
                    api_base: document.getElementById('apiBase').value || null,
                    access_level: document.getElementById('accessLevel').value,
                    allow_package_install: document.getElementById('allowPackageInstall').checked,
                    allow_tool_download: document.getElementById('allowToolDownload').checked,
                    allow_network_config: document.getElementById('allowNetworkConfig').checked,
                    allow_system_modification: document.getElementById('allowSystemMod').checked,
                    command_timeout: parseInt(document.getElementById('commandTimeout').value),
                    focus_areas: selectedFocusAreas,
                    
                    // Agent behavior
                    planning_depth: document.getElementById('planningDepth').value,
                    memory_strategy: document.getElementById('memoryStrategy').value,
                    enable_multi_agent: document.getElementById('enableMultiAgent').checked,
                    enable_browser_automation: document.getElementById('enableBrowser').checked,
                    enable_proxy_interception: document.getElementById('enableProxy').checked,
                    enable_web_search: document.getElementById('enableWebSearch').checked,
                    chain_attacks: document.getElementById('chainAttacks').checked,
                    auto_pivot: document.getElementById('autoPivot').checked,
                    aggressive_mode: document.getElementById('aggressiveMode').checked,
                    stealth_mode: document.getElementById('stealthMode').checked,
                    rate_limit_rps: parseInt(document.getElementById('rateLimit').value),
                    
                    // Output
                    output_format: document.getElementById('outputFormat').value,
                    severity_threshold: document.getElementById('severityThreshold').value,
                    save_artifacts: document.getElementById('saveArtifacts').checked,
                    include_screenshots: document.getElementById('includeScreenshots').checked,
                    include_poc: document.getElementById('includePoc').checked,
                    export_sarif: document.getElementById('exportSarif').checked,
                    notification_webhook: document.getElementById('webhook').value || null,
                };
                
                // Save configuration
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
                
                // Start scan
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
        fetchAndRenderModels();  // Fetch available models on page load
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
