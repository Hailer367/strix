"""
Strix Dashboard Module

Provides a web-based configuration dashboard for autonomous bug bounty operations
through GitHub Actions.

Features:
- Configure-and-Fire: Set all parameters before starting autonomous scan
- Roo Code Authentication: OAuth login for free AI models
- Real-time Monitoring: Live progress and findings display
- Extensible Configuration: Custom instructions, focus areas, and more
"""

from .server import create_app, run_dashboard
from .config import DashboardConfig, ScanConfig

__all__ = [
    "create_app",
    "run_dashboard",
    "DashboardConfig",
    "ScanConfig",
]
