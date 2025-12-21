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
#
# IMPORTANT: The chat.qwen.ai endpoint is NOT an OpenAI-compatible API.
# It's designed for the qwen-code CLI's internal use only.
#
# For LiteLLM integration, we MUST use one of these OpenAI-compatible endpoints:
# 1. DashScope API (Alibaba Cloud) - https://dashscope.aliyuncs.com/compatible-mode/v1
# 2. OpenRouter - https://openrouter.ai/api/v1
# 3. ModelScope - https://api-inference.modelscope.cn/v1
#
# Reference: https://qwenlm.github.io/qwen-code-docs/en/users/configuration/auth/

# OAuth endpoints (for device authorization flow)
QWENCODE_AUTH_URL = "https://chat.qwen.ai"
QWENCODE_DEVICE_AUTH_URL = "https://chat.qwen.ai/api/v1/oauth2/device/code"
QWENCODE_DEVICE_TOKEN_URL = "https://chat.qwen.ai/api/v1/oauth2/token"
QWENCODE_AUTHORIZE_URL = "https://chat.qwen.ai/authorize"

# Official OAuth client ID from qwen-code source
QWENCODE_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
QWENCODE_OAUTH_SCOPE = "openid profile email model.completion"
QWENCODE_OAUTH_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"

# OpenAI-compatible API endpoints that actually work with LiteLLM
# These are the endpoints that support the OpenAI API format
QWENCODE_DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWENCODE_MODELSCOPE_API_URL = "https://api-inference.modelscope.cn/v1"
QWENCODE_OPENROUTER_API_URL = "https://openrouter.ai/api/v1"

# Legacy endpoints (DO NOT USE for LiteLLM - kept for reference only)
# These are for the qwen-code CLI internal use
_QWENCODE_CHAT_API_URL = "https://chat.qwen.ai/api/v1"  # NOT OpenAI-compatible

# OAuth Device Authorization Flow endpoints (per official qwen-code CLI)
QWENCODE_DEVICE_CODE_ENDPOINT = QWENCODE_DEVICE_AUTH_URL
QWENCODE_DEVICE_TOKEN_ENDPOINT = QWENCODE_DEVICE_TOKEN_URL

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
    
    API providers for LiteLLM integration:
    1. dashscope: DashScope API (Alibaba Cloud) - OpenAI-compatible, recommended
    2. openrouter: OpenRouter - 1,000 free requests/day
    3. modelscope: ModelScope API - OpenAI-compatible
    4. qwen_oauth: Legacy - NOTE: chat.qwen.ai is NOT OpenAI-compatible, 
                   tokens from this flow should be used with DashScope instead
    
    IMPORTANT: The chat.qwen.ai/api/v1 endpoint is NOT an OpenAI-compatible API.
    Tokens obtained from Qwen OAuth must be used with DashScope or other
    OpenAI-compatible endpoints.
    """

    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    user_email: str | None = None
    user_id: str | None = None
    session_token: str | None = None  # For session-based auth
    resource_url: str | None = None  # API resource URL from OAuth response
    api_provider: str = "dashscope"  # dashscope, openrouter, modelscope, or qwen_oauth (legacy)

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
            "resource_url": self.resource_url,
            "api_provider": self.api_provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QwenCodeCredentials":
        """Create credentials from dictionary."""
        # Migrate legacy qwen_oauth to dashscope
        api_provider = data.get("api_provider", "qwen_oauth")
        if api_provider == "qwen_oauth":
            api_provider = "dashscope"  # Use OpenAI-compatible endpoint
        
        return cls(
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            user_email=data.get("user_email"),
            user_id=data.get("user_id"),
            session_token=data.get("session_token"),
            resource_url=data.get("resource_url"),
            api_provider=api_provider,
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

    def _initiate_device_auth(self) -> dict[str, Any] | None:
        """
        Initiate OAuth Device Authorization Flow.
        
        This is the proper authentication method used by the official qwen-code CLI.
        Reference: https://github.com/QwenLM/qwen-code
        
        Returns:
            Dictionary with device_code, user_code, verification_uri, etc. or None on failure
        """
        try:
            with httpx.Client(timeout=30) as client:
                # Request device code from Qwen OAuth server
                response = client.post(
                    QWENCODE_DEVICE_CODE_ENDPOINT,
                    json={
                        "client_id": QWENCODE_CLIENT_ID,
                        "scope": "openid profile email"
                    },
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "qwen-code-strix/1.0"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info("Device authorization initiated successfully")
                    return data
                else:
                    logger.warning(f"Device auth request failed: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.warning(f"Failed to initiate device authorization: {e}")
        
        return None

    def _poll_for_token(self, device_code: str, interval: int = 5, timeout: int = 300) -> str | None:
        """
        Poll the token endpoint for the access token.
        
        This is part of the OAuth Device Authorization Flow.
        
        Args:
            device_code: The device code received from device auth initiation
            interval: Polling interval in seconds
            timeout: Maximum time to wait for token
            
        Returns:
            Access token if successful, None otherwise
        """
        start_time = time.time()
        poll_interval = max(interval, 5)  # Minimum 5 seconds per OAuth spec
        
        while time.time() - start_time < timeout:
            time.sleep(poll_interval)
            
            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        QWENCODE_DEVICE_TOKEN_ENDPOINT,
                        json={
                            "client_id": QWENCODE_CLIENT_ID,
                            "device_code": device_code,
                            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                        },
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "qwen-code-strix/1.0"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        access_token = data.get("access_token")
                        if access_token:
                            logger.info("Token obtained successfully via device flow")
                            return access_token
                            
                    elif response.status_code == 400:
                        data = response.json()
                        error = data.get("error", "")
                        
                        if error == "authorization_pending":
                            # User hasn't authorized yet, continue polling
                            continue
                        elif error == "slow_down":
                            # Need to slow down polling
                            poll_interval += 5
                            continue
                        elif error == "expired_token":
                            logger.warning("Device code expired")
                            return None
                        elif error == "access_denied":
                            logger.warning("Access denied by user")
                            return None
                        else:
                            logger.warning(f"Token request error: {error}")
                            
            except Exception as e:
                logger.warning(f"Token polling error: {e}")
        
        logger.warning("Token polling timed out")
        return None

    def get_device_auth_url(self) -> tuple[str, str | None, str | None]:
        """
        Get the device authorization URL for display to the user.
        
        This is useful for headless/CI environments where the user needs
        to authenticate on a different device.
        
        Returns:
            Tuple of (auth_url, user_code, device_code)
        """
        device_auth = self._initiate_device_auth()
        
        if device_auth:
            verification_uri = device_auth.get("verification_uri", QWENCODE_AUTHORIZE_URL)
            verification_uri_complete = device_auth.get("verification_uri_complete")
            user_code = device_auth.get("user_code")
            device_code = device_auth.get("device_code")
            
            # Prefer the complete URI with user_code embedded
            if verification_uri_complete:
                auth_url = verification_uri_complete
            elif user_code:
                auth_url = f"{verification_uri}?user_code={user_code}&client={QWENCODE_CLIENT_ID}"
            else:
                auth_url = verification_uri
                
            return auth_url, user_code, device_code
        
        # Fallback URL
        return f"{QWENCODE_AUTHORIZE_URL}?client={QWENCODE_CLIENT_ID}", None, None

    def login(self, timeout: int = 300) -> bool:
        """
        Initiate OAuth login flow for Qwen Code CLI.

        This uses the OAuth Device Authorization Flow, which is the same
        method used by the official qwen-code CLI. It's suitable for both
        interactive and headless environments.

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
        manual_token = os.getenv("QWENCODE_ACCESS_TOKEN") or os.getenv("QWENCODE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if manual_token:
            # Determine the provider based on environment variables
            api_base = os.getenv("QWENCODE_API_BASE") or os.getenv("OPENAI_BASE_URL") or ""
            api_base_lower = api_base.lower()
            
            if "openrouter" in api_base_lower:
                api_provider = "openrouter"
            elif "modelscope" in api_base_lower:
                api_provider = "modelscope"
            elif "dashscope" in api_base_lower or "aliyun" in api_base_lower:
                api_provider = "dashscope"
            else:
                # Default to dashscope (OpenAI-compatible endpoint)
                api_provider = "dashscope"
                
            self.credentials = QwenCodeCredentials(
                access_token=manual_token,
                expires_at=time.time() + 3600 * 24 * 365,  # 1 year for manual tokens
                api_provider=api_provider,
            )
            self._save_credentials()
            logger.info(f"Using manual Qwen Code access token (provider: {api_provider})")
            return True

        # Try Device Authorization Flow (preferred method per official qwen-code CLI)
        logger.info("Initiating OAuth Device Authorization Flow...")
        device_auth = self._initiate_device_auth()
        
        if device_auth:
            verification_uri = device_auth.get("verification_uri", QWENCODE_AUTHORIZE_URL)
            verification_uri_complete = device_auth.get("verification_uri_complete")
            user_code = device_auth.get("user_code")
            device_code = device_auth.get("device_code")
            expires_in = device_auth.get("expires_in", 600)
            interval = device_auth.get("interval", 5)
            
            # Build the auth URL
            if verification_uri_complete:
                auth_url = verification_uri_complete
            elif user_code:
                auth_url = f"{verification_uri}?user_code={user_code}&client={QWENCODE_CLIENT_ID}"
            else:
                auth_url = verification_uri
            
            print("\n🤖 Qwen Code OAuth Device Authorization")
            print("   ==========================================")
            print("")
            print("   Please open this URL in your browser:")
            print(f"   🔗 {auth_url}")
            print("")
            if user_code:
                print(f"   📋 User Code: {user_code}")
                print("")
            print(f"   ⏳ This code expires in {expires_in // 60} minutes")
            print("   ==========================================\n")
            
            # Try to open browser automatically
            try:
                webbrowser.open(auth_url)
            except Exception as e:
                logger.warning(f"Failed to open browser: {e}")
                print(f"   ⚠️  Could not open browser automatically: {e}")
            
            # Poll for token
            if device_code:
                access_token = self._poll_for_token(device_code, interval, min(timeout, expires_in))
                
                if access_token:
                    # IMPORTANT: Even though we got the token from chat.qwen.ai OAuth,
                    # we must use it with DashScope API (OpenAI-compatible) for LiteLLM
                    self.credentials = QwenCodeCredentials(
                        access_token=access_token,
                        expires_at=time.time() + 3600 * 24 * 30,  # 30 days
                        api_provider="dashscope",  # Use OpenAI-compatible endpoint
                    )
                    self._save_credentials()
                    logger.info("Successfully authenticated with Qwen Code CLI via device flow")
                    print("✅ Authentication successful!")
                    print("   Using DashScope API (OpenAI-compatible endpoint)")
                    return True
        
        # Fallback to local callback server method (for desktop environments)
        logger.info("Device flow failed, falling back to local callback server...")
        callback_port = 18766
        server = HTTPServer(("localhost", callback_port), QwenCodeAuthHandler)
        server.timeout = timeout

        # Reset auth handler state
        QwenCodeAuthHandler.credentials = None
        QwenCodeAuthHandler.auth_error = None

        # Start server in background thread
        server_thread = Thread(target=server.handle_request, daemon=True)
        server_thread.start()

        # Open browser for authentication with callback
        callback_url = f"http://localhost:{callback_port}/callback"
        auth_url = f"{QWENCODE_AUTHORIZE_URL}?redirect_uri={callback_url}&client={QWENCODE_CLIENT_ID}"

        logger.info(f"Opening browser for Qwen Code authentication: {auth_url}")
        print("\n🤖 Opening browser for Qwen Code CLI authentication...")
        print("   If the browser doesn't open, visit this URL:")
        print(f"   {auth_url}\n")

        try:
            webbrowser.open(auth_url)
        except Exception as e:
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
        """Get API base URL for LiteLLM integration.
        
        IMPORTANT: The chat.qwen.ai endpoint is NOT OpenAI-compatible.
        We must use DashScope, ModelScope, or OpenRouter instead.
        
        Returns:
            An OpenAI-compatible API base URL
        """
        # Check environment variable for custom API base first
        custom_base = os.getenv("QWENCODE_API_BASE") or os.getenv("OPENAI_BASE_URL")
        if custom_base:
            return custom_base
        
        if self.credentials:
            provider = self.credentials.api_provider
            if provider == "openrouter":
                return QWENCODE_OPENROUTER_API_URL
            elif provider == "dashscope":
                return QWENCODE_DASHSCOPE_API_URL
            elif provider == "modelscope":
                return QWENCODE_MODELSCOPE_API_URL
        
        # Default to DashScope API (Alibaba Cloud's OpenAI-compatible endpoint)
        # This is the ONLY correct endpoint for LiteLLM integration with Qwen models
        # The chat.qwen.ai endpoint is NOT OpenAI-compatible and will cause errors
        return QWENCODE_DASHSCOPE_API_URL

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
    
    IMPORTANT: This function configures the model to use OpenAI-compatible endpoints.
    The chat.qwen.ai endpoint is NOT compatible with LiteLLM's openai provider.
    
    For Qwen models, we use:
    - DashScope API (default): https://dashscope.aliyuncs.com/compatible-mode/v1
    - OpenRouter: https://openrouter.ai/api/v1
    - ModelScope: https://api-inference.modelscope.cn/v1

    Args:
        model_name: The Qwen Code model name (e.g., "qwencode/qwen3-coder-plus")

    Returns:
        Tuple of (model_id, api_key, api_base) configured for LiteLLM
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
    api_key = provider.get_api_key()
    api_base = provider.get_api_base()
    
    # Map model names to the correct format for each provider
    if api_provider == "openrouter":
        # OpenRouter uses format like "qwen/qwen3-coder:free"
        if clean_name.startswith("qwen/"):
            model_id = f"openrouter/{clean_name}"
        elif "free" in clean_name.lower():
            model_id = f"openrouter/qwen/qwen3-coder:free"
        else:
            model_id = f"openrouter/qwen/{clean_name}"
    elif api_provider == "modelscope":
        # ModelScope uses Qwen/ prefix
        if clean_name.startswith("Qwen/"):
            model_id = f"openai/{clean_name}"
        else:
            # Map common names to ModelScope model IDs
            modelscope_mapping = {
                "qwen3-coder-plus": "Qwen/Qwen3-Coder-Plus",
                "qwen3-coder-plus-latest": "Qwen/Qwen3-Coder-Plus-Latest",
                "qwen3-coder": "Qwen/Qwen3-Coder",
            }
            mapped_name = modelscope_mapping.get(clean_name, f"Qwen/{clean_name}")
            model_id = f"openai/{mapped_name}"
    else:
        # Default: DashScope API (Alibaba Cloud)
        # DashScope uses model names like "qwen-coder-plus-latest"
        dashscope_mapping = {
            "qwen3-coder-plus": "qwen-coder-plus-latest",
            "qwen3-coder-plus-latest": "qwen-coder-plus-latest", 
            "qwen3-coder": "qwen-coder-turbo",
            "qwen-coder-plus": "qwen-coder-plus-latest",
            "qwen-coder": "qwen-coder-turbo",
        }
        mapped_name = dashscope_mapping.get(clean_name, clean_name)
        model_id = f"openai/{mapped_name}"
    
    logger.info(f"Configured Qwen Code for LiteLLM: model={model_id}, api_base={api_base}")
    
    return model_id, api_key, api_base
