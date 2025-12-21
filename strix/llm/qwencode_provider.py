"""
Qwen Code CLI Provider Integration for Strix

This module provides integration with Qwen Code CLI's AI models,
allowing Strix to use Qwen Code's models for AI-powered penetration testing.

Qwen Code CLI provides TWO authentication methods:

1. Qwen OAuth (RECOMMENDED - Start in 30 seconds):
   - Just run 'qwen' command and follow browser authentication
   - 2,000 free requests per day
   - 60 requests per minute rate limit
   - NO token limits, NO regional limits
   - Automatic credential refresh
   - Zero cost for individual users

2. OpenAI-Compatible API (via OpenRouter):
   - Requires API key from OpenRouter
   - 1,000 free requests/day on free tier
   - Must go through qwen-code CLI for proper routing

Reference: https://github.com/QwenLM/qwen-code
Authentication: https://qwen.ai OAuth flow
"""

import json
import logging
import os
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx


logger = logging.getLogger(__name__)

# Qwen Code CLI API endpoints
# Based on the official documentation: https://github.com/QwenLM/qwen-code
# Qwen OAuth: 2,000 requests/day, 60 req/min, no token limits, no regional limits
QWENCODE_AUTH_URL = "https://chat.qwen.ai"
QWENCODE_OPENROUTER_API_URL = "https://openrouter.ai/api/v1"

# Default config file location
QWENCODE_CONFIG_DIR = Path.home() / ".strix"
QWENCODE_CONFIG_FILE = QWENCODE_CONFIG_DIR / "qwencode_config.json"

# Qwen Code CLI models - fetched dynamically when authenticated
# These are fallback models for offline scenarios
# Reference: https://github.com/QwenLM/qwen-code
#
# Two authentication methods:
# 1. Qwen OAuth: 2,000 requests/day, 60 req/min, no token limits, no regional limits
# 2. OpenRouter: 1,000 free requests/day (via qwen-code CLI)
QWENCODE_MODELS: dict[str, dict[str, Any]] = {
    "qwen3-coder-plus": {
        "name": "qwen3-coder-plus",
        "display_name": "Qwen3 Coder Plus",
        "description": "Advanced Qwen3 coding model with enhanced capabilities - 262K context",
        "context_window": 262000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "analysis"],
        "speed": "fast",
        "endpoint": "qwen_oauth",
    },
    "qwen3-coder-plus-latest": {
        "name": "qwen3-coder-plus-latest",
        "display_name": "Qwen3 Coder Plus (Latest)",
        "description": "Latest version of Qwen3 coding model",
        "context_window": 262000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat", "analysis"],
        "speed": "fast",
        "endpoint": "qwen_oauth",
    },
    "qwen3-coder": {
        "name": "qwen3-coder",
        "display_name": "Qwen3 Coder",
        "description": "Balanced coding model for general development tasks - 131K context",
        "context_window": 131000,
        "free": True,
        "provider": "qwencode",
        "capabilities": ["code", "chat"],
        "speed": "fast",
        "endpoint": "qwen_oauth",
    },
    "qwen/qwen3-coder:free": {
        "name": "qwen/qwen3-coder:free",
        "display_name": "Qwen3 Coder (OpenRouter)",
        "description": "Qwen3 Coder via OpenRouter - 1,000 free requests/day",
        "context_window": 128000,
        "free": True,
        "provider": "openrouter",
        "capabilities": ["code", "chat"],
        "speed": "fast",
        "endpoint": "openrouter",
    },
}


@dataclass
class QwenCodeCredentials:
    """Qwen Code CLI authentication credentials.
    
    Reference: https://github.com/QwenLM/qwen-code
    
    Two authentication methods:
    1. qwen_oauth: 2,000 requests/day, 60 req/min, no token limits, no regional limits
    2. openrouter: 1,000 free requests/day (via qwen-code CLI)
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    session_token: str | None = None  # For session-based auth
    api_provider: str = "qwen_oauth"  # qwen_oauth or openrouter

    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        # Add 5 minute buffer before actual expiration
        return time.time() >= (self.expires_at - 300)

    def to_dict(self) -> dict[str, Any]:
        """Convert credentials to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "user_email": self.user_email,
            "user_id": self.user_id,
            "session_token": self.session_token,
            "api_provider": self.api_provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QwenCodeCredentials":
        """Create credentials from dictionary."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            user_email=data.get("user_email"),
            user_id=data.get("user_id"),
            session_token=data.get("session_token"),
            api_provider=data.get("api_provider", "qwen_oauth"),
        )


class QwenCodeAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    credentials: QwenCodeCredentials | None = None
    auth_error: str | None = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress HTTP server logs."""
        pass

    def do_GET(self) -> None:
        """Handle GET request (OAuth callback)."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/callback":
            query_params = parse_qs(parsed_path.query)

            if "error" in query_params:
                QwenCodeAuthHandler.auth_error = query_params.get("error", ["Unknown error"])[0]
                self._send_error_response()
                return

            # Extract token from callback - handle multiple token formats
            token = (
                query_params.get("token", [None])[0]
                or query_params.get("access_token", [None])[0]
                or query_params.get("code", [None])[0]
            )
            
            session_token = query_params.get("session_token", [None])[0]
            
            if token:
                QwenCodeAuthHandler.credentials = QwenCodeCredentials(
                    access_token=token,
                    session_token=session_token,
                    expires_at=time.time() + 3600 * 24 * 30,  # 30 days default
                    api_provider="qwen_oauth",
                )
                self._send_success_response()
            else:
                QwenCodeAuthHandler.auth_error = "No token received"
                self._send_error_response()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_success_response(self) -> None:
        """Send success response page."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        response = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Strix - Qwen Code Authentication</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       display: flex; justify-content: center; align-items: center; height: 100vh;
                       margin: 0; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }
                .container { text-align: center; padding: 40px; background: rgba(255,255,255,0.1);
                             border-radius: 16px; backdrop-filter: blur(10px); }
                h1 { color: #22c55e; margin-bottom: 16px; }
                p { color: #e5e5e5; }
                .icon { font-size: 64px; margin-bottom: 20px; }
            </style>
            <script>
                // Post message to opener and close
                setTimeout(() => {
                    if (window.opener) {
                        window.opener.postMessage({ type: 'qwencode_auth_success' }, '*');
                    }
                    window.close();
                }, 2000);
            </script>
        </head>
        <body>
            <div class="container">
                <div class="icon">🤖</div>
                <h1>Authentication Successful!</h1>
                <p>You can now close this window and return to Strix.</p>
                <p style="color: #22c55e; margin-top: 20px;">✓ Connected to Qwen Code CLI</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(response.encode())

    def _send_error_response(self) -> None:
        """Send error response page."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        error_msg = QwenCodeAuthHandler.auth_error or "Unknown error"
        response = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Strix - Authentication Error</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       display: flex; justify-content: center; align-items: center; height: 100vh;
                       margin: 0; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }}
                .container {{ text-align: center; padding: 40px; background: rgba(255,255,255,0.1);
                             border-radius: 16px; backdrop-filter: blur(10px); }}
                h1 {{ color: #ef4444; margin-bottom: 16px; }}
                p {{ color: #e5e5e5; }}
                .icon {{ font-size: 64px; margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">❌</div>
                <h1>Authentication Failed</h1>
                <p>Error: {error_msg}</p>
                <p style="margin-top: 20px;">Please try again or check your credentials.</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(response.encode())


class QwenCodeProvider:
    """
    Qwen Code CLI Provider for Strix.

    This provider allows Strix to use Qwen Code CLI's AI models for
    penetration testing. Supports TWO authentication methods:
    
    1. Qwen OAuth (RECOMMENDED):
       - Run 'qwen' command and follow browser authentication
       - 2,000 free requests per day
       - 60 requests per minute rate limit
       - NO token limits, NO regional limits
       - Automatic credential refresh
    
    2. OpenRouter (via qwen-code CLI):
       - Set QWENCODE_API_KEY or OPENAI_API_KEY environment variable
       - 1,000 free requests/day on free tier
    
    Reference: https://github.com/QwenLM/qwen-code
    """

    def __init__(self) -> None:
        self.credentials: QwenCodeCredentials | None = None
        self._cached_models: dict[str, dict[str, Any]] | None = None
        self._models_cache_time: float = 0
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load saved credentials from config file."""
        if QWENCODE_CONFIG_FILE.exists():
            try:
                with open(QWENCODE_CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    self.credentials = QwenCodeCredentials.from_dict(data)
                    logger.info("Loaded Qwen Code credentials from config")
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Failed to load Qwen Code credentials: {e}")
                self.credentials = None

    def _save_credentials(self) -> None:
        """Save credentials to config file."""
        if self.credentials is None:
            return

        try:
            QWENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(QWENCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.credentials.to_dict(), f, indent=2)
            # Secure the config file
            QWENCODE_CONFIG_FILE.chmod(0o600)
            logger.info("Saved Qwen Code credentials to config")
        except OSError as e:
            logger.warning(f"Failed to save Qwen Code credentials: {e}")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with Qwen Code CLI."""
        if self.credentials is None:
            return False
        if self.credentials.is_expired():
            return self._refresh_token()
        return bool(self.credentials.access_token)

    def _refresh_token(self) -> bool:
        """Attempt to refresh the access token."""
        if self.credentials is None or self.credentials.refresh_token is None:
            return False

        # For OAuth-based auth, refresh tokens may not be supported
        # Return False to trigger re-authentication
        logger.warning("Token refresh not supported for Qwen Code OAuth, re-authentication required")
        return False

    def login(self, timeout: int = 300) -> bool:
        """
        Initiate OAuth login flow for Qwen Code CLI.

        This opens a browser window for the user to authenticate with
        their qwen.ai account.

        Args:
            timeout: Maximum time to wait for authentication (seconds)

        Returns:
            True if authentication was successful, False otherwise
        """
        # Check for existing valid credentials
        if self.is_authenticated():
            logger.info("Already authenticated with Qwen Code CLI")
            return True

        # Check for manual token configuration
        manual_token = os.getenv("QWENCODE_ACCESS_TOKEN") or os.getenv("QWENCODE_API_KEY")
        if manual_token:
            # Determine the provider based on environment variables
            api_base = os.getenv("QWENCODE_API_BASE", "")
            if "openrouter" in api_base.lower():
                api_provider = "openrouter"
            else:
                api_provider = "qwen_oauth"
                
            self.credentials = QwenCodeCredentials(
                access_token=manual_token,
                expires_at=time.time() + 3600 * 24 * 365,  # 1 year for manual tokens
                api_provider=api_provider,
            )
            self._save_credentials()
            logger.info(f"Using manual Qwen Code access token (provider: {api_provider})")
            return True

        # Start local callback server
        callback_port = 18766  # Different port from Roo Code
        server = HTTPServer(("localhost", callback_port), QwenCodeAuthHandler)
        server.timeout = timeout

        # Reset auth handler state
        QwenCodeAuthHandler.credentials = None
        QwenCodeAuthHandler.auth_error = None

        # Start server in background thread
        server_thread = Thread(target=server.handle_request, daemon=True)
        server_thread.start()

        # Open browser for authentication
        callback_url = f"http://localhost:{callback_port}/callback"
        # Use the Qwen AI sign-in page with redirect
        auth_url = f"{QWENCODE_AUTH_URL}/?redirect_uri={callback_url}&app=strix"

        logger.info(f"Opening browser for Qwen Code authentication: {auth_url}")
        print("\n🤖 Opening browser for Qwen Code CLI authentication...")
        print("   If the browser doesn't open, visit this URL:")
        print(f"   {auth_url}\n")

        try:
            webbrowser.open(auth_url)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to open browser: {e}")
            print(f"   ⚠️  Could not open browser automatically: {e}")

        # Wait for authentication
        server_thread.join(timeout=timeout)
        server.server_close()

        if QwenCodeAuthHandler.credentials:
            self.credentials = QwenCodeAuthHandler.credentials
            self._save_credentials()
            logger.info("Successfully authenticated with Qwen Code CLI")
            return True

        if QwenCodeAuthHandler.auth_error:
            logger.error(f"Qwen Code authentication failed: {QwenCodeAuthHandler.auth_error}")

        return False

    def logout(self) -> None:
        """Clear stored credentials and log out."""
        self.credentials = None
        self._cached_models = None
        if QWENCODE_CONFIG_FILE.exists():
            try:
                QWENCODE_CONFIG_FILE.unlink()
                logger.info("Logged out from Qwen Code CLI")
            except OSError as e:
                logger.warning(f"Failed to remove credentials file: {e}")

    def get_api_key(self) -> str | None:
        """Get API key for LiteLLM integration."""
        if not self.is_authenticated():
            return None
        return self.credentials.access_token if self.credentials else None

    def get_api_base(self) -> str:
        """Get API base URL for LiteLLM integration."""
        if self.credentials:
            provider = self.credentials.api_provider
            if provider == "openrouter":
                return QWENCODE_OPENROUTER_API_URL
        
        # Check environment variable for custom API base
        custom_base = os.getenv("QWENCODE_API_BASE")
        if custom_base:
            return custom_base
            
        # Default to Qwen OAuth API
        return f"{QWENCODE_AUTH_URL}/api/v1"

    def fetch_available_models(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """
        Fetch available models from Qwen Code CLI API.
        
        This attempts to get the latest models from the API,
        with fallback to hardcoded defaults if the API is unavailable.
        
        Args:
            force_refresh: Force refresh from API even if cache is valid
            
        Returns:
            Dictionary of available models
        """
        # Use cached models if available and not expired (cache for 1 hour)
        cache_ttl = 3600  # 1 hour
        if (
            not force_refresh
            and self._cached_models
            and (time.time() - self._models_cache_time) < cache_ttl
        ):
            return self._cached_models

        # Try to fetch from API
        if self.is_authenticated():
            api_base = self.get_api_base()
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{api_base}/models",
                        headers={"Authorization": f"Bearer {self.credentials.access_token}"},
                        timeout=30,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        models = {}
                        for model in data.get("data", []):
                            model_id = model.get("id", "")
                            if model_id and ("qwen" in model_id.lower() or "coder" in model_id.lower()):
                                models[model_id] = {
                                    "name": model_id,
                                    "display_name": model.get("name", model_id),
                                    "description": model.get("description", "Qwen Code model"),
                                    "context_window": model.get("context_length", 128000),
                                    "free": model.get("pricing", {}).get("free", False),
                                    "provider": self.credentials.api_provider if self.credentials else "qwencode",
                                    "capabilities": model.get("capabilities", ["code", "chat"]),
                                }
                        if models:
                            self._cached_models = models
                            self._models_cache_time = time.time()
                            logger.info(f"Fetched {len(models)} models from Qwen Code API")
                            return models
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to fetch models from API: {e}")

        # Fallback to hardcoded models
        logger.info("Using default Qwen Code models")
        return QWENCODE_MODELS.copy()

    def get_available_models(self) -> dict[str, dict[str, Any]]:
        """Get list of available Qwen Code models."""
        return self.fetch_available_models()

    def get_model_id(self, model_name: str) -> str:
        """
        Convert Qwen Code model name to provider model ID.

        Args:
            model_name: Qwen Code model name (e.g., "qwen3-coder-plus")

        Returns:
            Provider-compatible model ID for LiteLLM
        """
        # Clean the model name
        clean_name = model_name.replace("qwencode/", "")
        
        # Get available models
        models = self.get_available_models()
        
        if clean_name in models:
            # Use direct model ID for Qwen Code API
            return f"qwencode/{clean_name}"
        
        # If model not found in available models, return as-is
        return f"qwencode/{clean_name}"

    def get_user_info(self) -> dict[str, Any] | None:
        """Get current user information."""
        if not self.is_authenticated():
            return None

        return {
            "email": self.credentials.user_email if self.credentials else None,
            "user_id": self.credentials.user_id if self.credentials else None,
            "authenticated": True,
            "api_provider": self.credentials.api_provider if self.credentials else None,
        }


# Global provider instance
_qwencode_provider: QwenCodeProvider | None = None


def get_qwencode_provider() -> QwenCodeProvider:
    """Get the global Qwen Code provider instance."""
    global _qwencode_provider
    if _qwencode_provider is None:
        _qwencode_provider = QwenCodeProvider()
    return _qwencode_provider


def is_qwencode_model(model_name: str) -> bool:
    """Check if a model name is a Qwen Code model."""
    if model_name.startswith("qwencode/"):
        return True
    clean_name = model_name.replace("qwencode/", "")
    provider = get_qwencode_provider()
    models = provider.get_available_models()
    return clean_name in models


def configure_qwencode_for_litellm(model_name: str) -> tuple[str, str | None, str | None]:
    """
    Configure LiteLLM parameters for Qwen Code model.

    Args:
        model_name: The Qwen Code model name

    Returns:
        Tuple of (model_id, api_key, api_base)
    """
    provider = get_qwencode_provider()

    if not provider.is_authenticated():
        raise RuntimeError(
            "Not authenticated with Qwen Code CLI. "
            "Please run 'strix --qwencode-login' or set QWENCODE_ACCESS_TOKEN/QWENCODE_API_KEY."
        )

    clean_name = model_name.replace("qwencode/", "")
    
    # Determine the correct model ID format based on provider
    api_provider = provider.credentials.api_provider if provider.credentials else "qwen_oauth"
    
    if api_provider == "openrouter":
        # OpenRouter uses format like "qwen/qwen3-coder:free"
        if not clean_name.startswith("qwen/"):
            model_id = f"openai/{clean_name}"  # LiteLLM format for OpenRouter
        else:
            model_id = f"openai/{clean_name}"
    else:
        # For Alibaba Cloud/ModelScope, use OpenAI-compatible format
        model_id = f"openai/{clean_name}"
    
    api_key = provider.get_api_key()
    api_base = provider.get_api_base()

    return model_id, api_key, api_base
