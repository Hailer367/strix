"""
Strix Web Server CLI - Command line interface for hosted mode
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


def get_version() -> str:
    try:
        from importlib.metadata import version
        return version("strix-agent")
    except Exception:
        return "0.5.0"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strix Web Server - Hosted mode for web dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with defaults (port 8000)
  strix-server

  # Start server on custom port
  strix-server --port 3000

  # Start server with custom host
  strix-server --host 127.0.0.1 --port 8080

  # Start with dashboard build
  strix-server --build-dashboard
        """,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"strix-server {get_version()}",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )

    parser.add_argument(
        "--build-dashboard",
        action="store_true",
        help="Build the Next.js dashboard before starting",
    )

    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run in development mode with auto-reload",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )

    return parser.parse_args()


def display_startup_message(host: str, port: int) -> None:
    console = Console()

    startup_text = Text()
    startup_text.append("🦉 ", style="bold white")
    startup_text.append("STRIX WEB SERVER", style="bold green")
    startup_text.append("\n\n", style="white")
    startup_text.append("Server running at:\n", style="white")
    startup_text.append(f"  • Local:   ", style="dim white")
    startup_text.append(f"http://localhost:{port}\n", style="bold cyan")
    if host == "0.0.0.0":
        startup_text.append(f"  • Network: ", style="dim white")
        startup_text.append(f"http://<your-ip>:{port}\n", style="bold cyan")
    startup_text.append("\n", style="white")
    startup_text.append("Endpoints:\n", style="white")
    startup_text.append(f"  • Dashboard:  ", style="dim white")
    startup_text.append(f"http://localhost:{port}\n", style="cyan")
    startup_text.append(f"  • API:        ", style="dim white")
    startup_text.append(f"http://localhost:{port}/api\n", style="cyan")
    startup_text.append(f"  • WebSocket:  ", style="dim white")
    startup_text.append(f"ws://localhost:{port}/ws\n", style="cyan")
    startup_text.append("\n", style="white")
    startup_text.append("Press ", style="dim white")
    startup_text.append("Ctrl+C", style="bold yellow")
    startup_text.append(" to stop the server", style="dim white")

    panel = Panel(
        startup_text,
        title="[bold green]🛡️  STRIX HOSTED MODE",
        title_align="center",
        border_style="green",
        padding=(1, 2),
    )

    console.print("\n")
    console.print(panel)
    console.print()


def build_dashboard() -> bool:
    """Build the Next.js dashboard"""
    console = Console()
    dashboard_dir = Path(__file__).parent.parent.parent / "web-dashboard"

    if not dashboard_dir.exists():
        console.print("[red]Error: web-dashboard directory not found[/red]")
        return False

    console.print("[cyan]Building dashboard...[/cyan]")

    import subprocess

    try:
        # Install dependencies
        subprocess.run(
            ["npm", "install"],
            cwd=dashboard_dir,
            check=True,
            capture_output=True,
        )

        # Build
        subprocess.run(
            ["npm", "run", "build"],
            cwd=dashboard_dir,
            check=True,
            capture_output=True,
        )

        console.print("[green]Dashboard built successfully![/green]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error building dashboard: {e}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]Error: npm not found. Please install Node.js[/red]")
        return False


def main() -> None:
    args = parse_arguments()

    # Build dashboard if requested
    if args.build_dashboard:
        if not build_dashboard():
            sys.exit(1)

    display_startup_message(args.host, args.port)

    # Start the server
    try:
        import uvicorn
        from strix.server.main import app

        uvicorn.run(
            "strix.server.main:app" if args.dev else app,
            host=args.host,
            port=args.port,
            reload=args.dev,
            workers=args.workers if not args.dev else 1,
            log_level="info",
        )
    except KeyboardInterrupt:
        console = Console()
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console = Console()
        console.print(f"\n[red]Error starting server: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
