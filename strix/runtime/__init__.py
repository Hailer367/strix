import os

from .runtime import AbstractRuntime


def get_runtime() -> AbstractRuntime:
    """Get runtime instance based on environment configuration.
    
    Auto-detects GitHub Actions environment and uses remote runtime if available.
    Otherwise falls back to Docker runtime.
    """
    # Check for explicit runtime backend setting
    runtime_backend = os.getenv("STRIX_RUNTIME_BACKEND", "")
    
    # Auto-detect GitHub Actions and remote server availability
    is_github_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
    has_cred_tunnel = bool(os.getenv("CRED_TUNNEL", ""))
    
    # Use remote runtime if:
    # 1. Explicitly set to "remote"
    # 2. In GitHub Actions AND CRED_TUNNEL is available
    # 3. STRIX_SERVER_URL is set
    if runtime_backend == "remote" or (is_github_actions and has_cred_tunnel) or os.getenv("STRIX_SERVER_URL"):
        from .remote_runtime import RemoteRuntime

        return RemoteRuntime()
    
    # Default to Docker runtime
    if runtime_backend == "docker" or not runtime_backend:
        from .docker_runtime import DockerRuntime

        return DockerRuntime()

    raise ValueError(
        f"Unsupported runtime backend: {runtime_backend}. "
        f"Supported backends: 'docker', 'remote'"
    )


__all__ = ["AbstractRuntime", "get_runtime"]
