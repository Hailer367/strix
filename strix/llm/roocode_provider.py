"""
Roo Code Cloud Provider Integration for Strix

This module provides integration with Roo Code Cloud's AI models,
allowing Strix to use Roo Code Cloud's models for AI-powered penetration testing.

Roo Code Cloud provides:
- Zero configuration: Easy OAuth authentication
- Free Premium Models: Access to grok-code-fast-1 and code-supernova
- OAuth authentication via GitHub, Google, or email

Reference: https://docs.roocode.com/providers/roo-code-cloud
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

# Roo Code Cloud API endpoints
# Based on the official documentation: https://docs.roocode.com/roo-code-cloud/overview
ROOCODE_AUTH_URL = "https://app.roocode.com"
ROOCODE_API_URL = "https://api.roocode.com"
# Roo Code Cloud uses an OpenAI-compatible API for inference
ROOCODE_INFERENCE_URL = "https://api.roocode.com/v1"

# Default config file location
ROOCODE_CONFIG_DIR = Path.home() / ".strix"
ROOCODE_CONFIG_FILE = ROOCODE_CONFIG_DIR / "roocode_config.json"

# Fallback Roo Code Cloud models - used when API is unavailable
# Based on official documentation: https://docs.roocode.com/providers/roo-code-cloud
# NOTE: Models should be fetched dynamically from the API when authenticated.
# These fallback models are provided only for offline scenarios.
ROOCODE_MODELS: dict = {
    # Empty by default to force API fetch after authentication
    # This prevents showing potentially outdated model information
}


@dataclass
class RooCodeCredentials:
    """Roo Code Cloud authentication credentials."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    session_token: str | None = None  # For session-based auth

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RooCodeCredentials":
        """Create credentials from dictionary."""
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            user_email=data.get("user_email"),
            user_id=data.get("user_id"),
            session_token=data.get("session_token"),
        )


class RooCodeAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    credentials: RooCodeCredentials | None = None
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
                RooCodeAuthHandler.auth_error = query_params.get("error", ["Unknown error"])[0]
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
                RooCodeAuthHandler.credentials = RooCodeCredentials(
                    access_token=token,
                    session_token=session_token,
                    expires_at=time.time() + 3600 * 24 * 30,  # 30 days default
                )
                self._send_success_response()
            else:
                RooCodeAuthHandler.auth_error = "No token received"
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
            <title>Strix - Roo Code Authentication</title>
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
                        window.opener.postMessage({ type: 'roocode_auth_success' }, '*');
                    }
                    window.close();
                }, 2000);
            </script>
        </head>
        <body>
            <div class="container">
                <div class="icon">🦉</div>
                <h1>Authentication Successful!</h1>
                <p>You can now close this window and return to Strix.</p>
                <p style="color: #22c55e; margin-top: 20px;">✓ Connected to Roo Code Cloud</p>
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
        error_msg = RooCodeAuthHandler.auth_error or "Unknown error"
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


class RooCodeProvider:
    """
    Roo Code Cloud Provider for Strix.

    This provider allows Strix to use Roo Code Cloud's AI models for
    penetration testing without requiring separate API keys.
    
    Authentication methods:
    1. Manual token via ROOCODE_ACCESS_TOKEN environment variable
    2. OAuth flow via browser (opens app.roocode.com)
    """

    def __init__(self) -> None:
        self.credentials: RooCodeCredentials | None = None
        self._cached_models: dict[str, dict[str, Any]] | None = None
        self._models_cache_time: float = 0
        self._load_credentials()

    def _load_credentials(self) -> None:
        """Load saved credentials from config file."""
        if ROOCODE_CONFIG_FILE.exists():
            try:
                with open(ROOCODE_CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    self.credentials = RooCodeCredentials.from_dict(data)
                    logger.info("Loaded Roo Code credentials from config")
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Failed to load Roo Code credentials: {e}")
                self.credentials = None

    def _save_credentials(self) -> None:
        """Save credentials to config file."""
        if self.credentials is None:
            return

        try:
            ROOCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(ROOCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.credentials.to_dict(), f, indent=2)
            # Secure the config file
            ROOCODE_CONFIG_FILE.chmod(0o600)
            logger.info("Saved Roo Code credentials to config")
        except OSError as e:
            logger.warning(f"Failed to save Roo Code credentials: {e}")

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with Roo Code Cloud."""
        if self.credentials is None:
            return False
        if self.credentials.is_expired():
            return self._refresh_token()
        return bool(self.credentials.access_token)

    def _refresh_token(self) -> bool:
        """Attempt to refresh the access token."""
        if self.credentials is None or self.credentials.refresh_token is None:
            return False

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ROOCODE_API_URL}/v1/auth/refresh",
                    json={"refresh_token": self.credentials.refresh_token},
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    self.credentials.access_token = data.get("access_token", self.credentials.access_token)
                    self.credentials.expires_at = time.time() + data.get("expires_in", 3600 * 24)
                    if "refresh_token" in data:
                        self.credentials.refresh_token = data["refresh_token"]
                    self._save_credentials()
                    logger.info("Successfully refreshed Roo Code token")
                    return True
                else:
                    logger.warning(f"Token refresh failed with status: {response.status_code}")
                    return False

        except (httpx.RequestError, httpx.HTTPStatusError, KeyError) as e:
            logger.warning(f"Failed to refresh Roo Code token: {e}")
            return False

    def login(self, timeout: int = 300) -> bool:
        """
        Initiate OAuth login flow for Roo Code Cloud.

        This opens a browser window for the user to authenticate with
        GitHub, Google, or email through Roo Code Cloud.

        Args:
            timeout: Maximum time to wait for authentication (seconds)

        Returns:
            True if authentication was successful, False otherwise
        """
        # Check for existing valid credentials
        if self.is_authenticated():
            logger.info("Already authenticated with Roo Code Cloud")
            return True

        # Check for manual token configuration
        manual_token = os.getenv("ROOCODE_ACCESS_TOKEN")
        if manual_token:
            self.credentials = RooCodeCredentials(
                access_token=manual_token,
                expires_at=time.time() + 3600 * 24 * 365,  # 1 year for manual tokens
            )
            self._save_credentials()
            logger.info("Using manual Roo Code access token")
            return True

        # Start local callback server
        callback_port = 18765
        server = HTTPServer(("localhost", callback_port), RooCodeAuthHandler)
        server.timeout = timeout

        # Reset auth handler state
        RooCodeAuthHandler.credentials = None
        RooCodeAuthHandler.auth_error = None

        # Start server in background thread
        server_thread = Thread(target=server.handle_request, daemon=True)
        server_thread.start()

        # Open browser for authentication
        callback_url = f"http://localhost:{callback_port}/callback"
        # Use the sign-in page with redirect
        auth_url = f"{ROOCODE_AUTH_URL}/sign-in?redirect_uri={callback_url}&app=strix"

        logger.info(f"Opening browser for Roo Code authentication: {auth_url}")
        print("\n🦉 Opening browser for Roo Code Cloud authentication...")
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

        if RooCodeAuthHandler.credentials:
            self.credentials = RooCodeAuthHandler.credentials
            self._save_credentials()
            logger.info("Successfully authenticated with Roo Code Cloud")
            return True

        if RooCodeAuthHandler.auth_error:
            logger.error(f"Roo Code authentication failed: {RooCodeAuthHandler.auth_error}")

        return False

    def logout(self) -> None:
        """Clear stored credentials and log out."""
        self.credentials = None
        self._cached_models = None
        if ROOCODE_CONFIG_FILE.exists():
            try:
                ROOCODE_CONFIG_FILE.unlink()
                logger.info("Logged out from Roo Code Cloud")
            except OSError as e:
                logger.warning(f"Failed to remove credentials file: {e}")

    def get_api_key(self) -> str | None:
        """Get API key for LiteLLM integration."""
        if not self.is_authenticated():
            return None
        return self.credentials.access_token if self.credentials else None

    def get_api_base(self) -> str:
        """Get API base URL for LiteLLM integration."""
        return ROOCODE_INFERENCE_URL

    def fetch_available_models(self, force_refresh: bool = False) -> dict[str, dict[str, Any]]:
        """
        Fetch available models from Roo Code Cloud API.
        
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
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{ROOCODE_API_URL}/v1/models",
                        headers={"Authorization": f"Bearer {self.credentials.access_token}"},
                        timeout=30,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        models = {}
                        for model in data.get("data", []):
                            model_id = model.get("id", "")
                            if model_id:
                                models[model_id] = {
                                    "name": model_id,
                                    "display_name": model.get("name", model_id),
                                    "description": model.get("description", ""),
                                    "context_window": model.get("context_length", 128000),
                                    "free": model.get("pricing", {}).get("free", False),
                                    "provider": model.get("provider", "roocode"),
                                    "capabilities": model.get("capabilities", ["code", "chat"]),
                                }
                        if models:
                            self._cached_models = models
                            self._models_cache_time = time.time()
                            logger.info(f"Fetched {len(models)} models from Roo Code Cloud API")
                            return models
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to fetch models from API: {e}")

        # Fallback to hardcoded models
        logger.info("Using default Roo Code models")
        return ROOCODE_MODELS.copy()

    def get_available_models(self) -> dict[str, dict[str, Any]]:
        """Get list of available Roo Code models."""
        return self.fetch_available_models()

    def get_model_id(self, model_name: str) -> str:
        """
        Convert Roo Code model name to provider model ID.

        Args:
            model_name: Roo Code model name (e.g., "grok-code-fast-1")

        Returns:
            Provider-compatible model ID for LiteLLM
        """
        # Clean the model name
        clean_name = model_name.replace("roocode/", "")
        
        # Get available models
        models = self.get_available_models()
        
        if clean_name in models:
            # Use direct model ID for Roo Code Cloud API
            return f"roocode/{clean_name}"
        
        # If model not found in available models, return as-is
        return f"roocode/{clean_name}"

    def get_user_info(self) -> dict[str, Any] | None:
        """Get current user information."""
        if not self.is_authenticated():
            return None

        # Try to fetch user info from API
        if self.credentials and self.credentials.access_token:
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"{ROOCODE_API_URL}/v1/user",
                        headers={"Authorization": f"Bearer {self.credentials.access_token}"},
                        timeout=30,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        self.credentials.user_email = data.get("email")
                        self.credentials.user_id = data.get("id")
                        self._save_credentials()
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Failed to fetch user info: {e}")

        return {
            "email": self.credentials.user_email if self.credentials else None,
            "user_id": self.credentials.user_id if self.credentials else None,
            "authenticated": True,
        }


# Global provider instance
_roocode_provider: RooCodeProvider | None = None


def get_roocode_provider() -> RooCodeProvider:
    """Get the global Roo Code provider instance."""
    global _roocode_provider
    if _roocode_provider is None:
        _roocode_provider = RooCodeProvider()
    return _roocode_provider


def is_roocode_model(model_name: str) -> bool:
    """Check if a model name is a Roo Code model."""
    if model_name.startswith("roocode/"):
        return True
    clean_name = model_name.replace("roocode/", "")
    provider = get_roocode_provider()
    models = provider.get_available_models()
    return clean_name in models


def configure_roocode_for_litellm(model_name: str) -> tuple[str, str | None, str | None]:
    """
    Configure LiteLLM parameters for Roo Code model.

    Args:
        model_name: The Roo Code model name

    Returns:
        Tuple of (model_id, api_key, api_base)
    """
    provider = get_roocode_provider()

    if not provider.is_authenticated():
        raise RuntimeError(
            "Not authenticated with Roo Code Cloud. "
            "Please run 'strix --roocode-login' or set ROOCODE_ACCESS_TOKEN."
        )

    clean_name = model_name.replace("roocode/", "")
    model_id = provider.get_model_id(clean_name)
    api_key = provider.get_api_key()
    api_base = provider.get_api_base()

    return model_id, api_key, api_base
