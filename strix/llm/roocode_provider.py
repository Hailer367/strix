"""
Roo Code Cloud Provider Integration for Strix

This module provides integration with Roo Code Cloud's free AI models,
allowing Strix to use Roo Code Cloud's grok-code-fast-1 and code-supernova
models for AI-powered penetration testing.

Roo Code Cloud provides:
- Zero configuration: No API keys to manage
- Free Premium Models: Access to grok-code-fast-1 and code-supernova
- OAuth authentication via GitHub, Google, or email
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
ROOCODE_AUTH_URL = "https://app.roocode.com"
ROOCODE_API_URL = "https://api.roocode.com"
ROOCODE_OPENAI_COMPATIBLE_URL = "https://openrouter.ai/api/v1"

# Available Roo Code Cloud models
ROOCODE_MODELS = {
    "grok-code-fast-1": {
        "name": "grok-code-fast-1",
        "description": "Fast coding model - Best for quick edits and high-speed iterations",
        "context_window": 262000,
        "free": True,
        "openrouter_id": "x-ai/grok-2-1212",
    },
    "roo/code-supernova": {
        "name": "roo/code-supernova",
        "description": "Advanced model - Best for complex reasoning and multimodal tasks",
        "context_window": 200000,
        "free": True,
        "openrouter_id": "openai/gpt-4o",
    },
}

# Default config file location
ROOCODE_CONFIG_DIR = Path.home() / ".strix"
ROOCODE_CONFIG_FILE = ROOCODE_CONFIG_DIR / "roocode_config.json"


@dataclass
class RooCodeCredentials:
    """Roo Code Cloud authentication credentials."""

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None

    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """Convert credentials to dictionary."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "user_email": self.user_email,
            "user_id": self.user_id,
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

            # Extract token from callback
            token = query_params.get("token", [None])[0]
            if token:
                RooCodeAuthHandler.credentials = RooCodeCredentials(
                    access_token=token,
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
    penetration testing without requiring OpenAI API keys.
    """

    def __init__(self) -> None:
        self.credentials: RooCodeCredentials | None = None
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
        return True

    def _refresh_token(self) -> bool:
        """Attempt to refresh the access token."""
        if self.credentials is None or self.credentials.refresh_token is None:
            return False

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{ROOCODE_API_URL}/auth/refresh",
                    json={"refresh_token": self.credentials.refresh_token},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                self.credentials.access_token = data["access_token"]
                self.credentials.expires_at = time.time() + data.get("expires_in", 3600 * 24)
                if "refresh_token" in data:
                    self.credentials.refresh_token = data["refresh_token"]

                self._save_credentials()
                logger.info("Successfully refreshed Roo Code token")
                return True

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
        auth_url = f"{ROOCODE_AUTH_URL}/auth/cli?callback={callback_url}&app=strix"

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
        # Roo Code Cloud uses OpenRouter-compatible API
        return ROOCODE_OPENAI_COMPATIBLE_URL

    def get_available_models(self) -> dict[str, dict[str, Any]]:
        """Get list of available Roo Code models."""
        return ROOCODE_MODELS.copy()

    def get_model_id(self, model_name: str) -> str:
        """
        Convert Roo Code model name to provider model ID.

        Args:
            model_name: Roo Code model name (e.g., "grok-code-fast-1")

        Returns:
            Provider-compatible model ID for LiteLLM
        """
        if model_name in ROOCODE_MODELS:
            # Return OpenRouter-compatible ID for LiteLLM
            return f"openrouter/{ROOCODE_MODELS[model_name]['openrouter_id']}"
        return model_name

    def get_user_info(self) -> dict[str, Any] | None:
        """Get current user information."""
        if not self.is_authenticated():
            return None

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
    return clean_name in ROOCODE_MODELS


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
