#!/usr/bin/env python3
"""
Strix Agent Interface - GitHub Actions Edition

A powerful AI-driven penetration testing and bug bounty automation agent
designed for GitHub Actions CI/CD workflows.

This tool is optimized for:
- Running as a GitHub Actions workflow
- Web dashboard configuration via Cloudflare tunnel
- Autonomous long-running security scans
- Integration with Roo Code Cloud and Qwen Code CLI for free AI models

Local Usage:
  While this tool is designed for GitHub Actions, you can run it locally
  for testing with: strix --target <url>
  
GitHub Actions Usage:
  1. Configure the workflow in .github/workflows/strix-dashboard.yml
  2. Add ROOCODE_ACCESS_TOKEN to repository secrets (optional)
  3. Run the workflow from GitHub Actions tab
  4. Access the dashboard via the Cloudflare tunnel URL
  5. Configure scan parameters and click "Configure and Fire"
"""

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import litellm
from docker.errors import DockerException
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from strix.interface.cli import run_cli
from strix.interface.tui import run_tui
from strix.interface.utils import (
    assign_workspace_subdirs,
    build_final_stats_text,
    check_docker_connection,
    clone_repository,
    collect_local_sources,
    generate_run_name,
    image_exists,
    infer_target_type,
    process_pull_line,
    validate_llm_response,
)
from strix.llm.roocode_provider import get_roocode_provider, ROOCODE_MODELS
from strix.llm.qwencode_provider import get_qwencode_provider, QWENCODE_MODELS
from strix.runtime.docker_runtime import STRIX_IMAGE
from strix.telemetry.tracer import get_global_tracer


logging.getLogger().setLevel(logging.ERROR)

# GitHub Actions environment detection
IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS", "").lower() == "true"
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_RUN_ID = os.getenv("GITHUB_RUN_ID", "")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "")


def is_github_actions() -> bool:
    """Check if running in GitHub Actions environment."""
    return IS_GITHUB_ACTIONS


def validate_environment(use_roocode: bool = False, use_qwencode: bool = False) -> None:  # noqa: PLR0912, PLR0915
    console = Console()
    missing_required_vars = []
    missing_optional_vars = []

    # Check if using Roo Code or Qwen Code provider
    strix_llm = os.getenv("STRIX_LLM", "")
    is_roocode = use_roocode or strix_llm.startswith("roocode/")
    is_qwencode = use_qwencode or strix_llm.startswith("qwencode/")

    if is_roocode:
        # Roo Code mode - no API keys required
        provider = get_roocode_provider()
        if not provider.is_authenticated():
            # In GitHub Actions, check for environment token first
            env_token = os.getenv("ROOCODE_ACCESS_TOKEN")
            if env_token:
                # Token available from environment (GitHub Actions secret)
                console.print("[bold green]✅ Using Roo Code token from environment[/]")
                os.environ["ROOCODE_ACCESS_TOKEN"] = env_token
            else:
                # Need to authenticate interactively
                console.print()
                console.print("[bold cyan]🦉 Roo Code Cloud Authentication Required[/]")
                console.print()

                if IS_GITHUB_ACTIONS:
                    # In GitHub Actions, we rely on the dashboard for auth
                    console.print("[bold yellow]⚠️  Please authenticate via the dashboard[/]")
                    console.print("   Open the dashboard URL and log in with Roo Code Cloud")
                    return

                if not provider.login():
                    error_text = Text()
                    error_text.append("❌ ", style="bold red")
                    error_text.append("ROO CODE AUTHENTICATION FAILED", style="bold red")
                    error_text.append("\n\n", style="white")
                    error_text.append(
                        "Could not authenticate with Roo Code Cloud.\n", style="white"
                    )
                    error_text.append(
                        "Please try again or set ROOCODE_ACCESS_TOKEN manually.\n", style="white"
                    )

                    panel = Panel(
                        error_text,
                        title="[bold red]🛡️  STRIX AUTHENTICATION ERROR",
                        title_align="center",
                        border_style="red",
                        padding=(1, 2),
                    )
                    console.print("\n")
                    console.print(panel)
                    console.print()
                    sys.exit(1)

                console.print("[bold green]✅ Successfully authenticated with Roo Code Cloud[/]")
                console.print()

        # Set default model if not specified
        if not strix_llm:
            os.environ["STRIX_LLM"] = "roocode/grok-code-fast-1"

        # Skip API key validation for Roo Code
        return

    if is_qwencode:
        # Qwen Code mode - check for API key or OAuth
        provider = get_qwencode_provider()
        if not provider.is_authenticated():
            env_token = os.getenv("QWENCODE_ACCESS_TOKEN") or os.getenv("QWENCODE_API_KEY")
            if env_token:
                console.print("[bold green]✅ Using Qwen Code token from environment[/]")
            else:
                if IS_GITHUB_ACTIONS:
                    console.print("[bold yellow]⚠️  Please authenticate via the dashboard[/]")
                    return
                
                if not provider.login():
                    console.print("[bold red]❌ Qwen Code authentication failed[/]")
                    sys.exit(1)
                console.print("[bold green]✅ Authenticated with Qwen Code CLI[/]")
        
        if not strix_llm:
            os.environ["STRIX_LLM"] = "qwencode/qwen3-coder-plus"
        return

    # Standard mode - check for API configuration
    if not strix_llm:
        missing_required_vars.append("STRIX_LLM")

    has_base_url = any(
        [
            os.getenv("LLM_API_BASE"),
            os.getenv("OPENAI_API_BASE"),
            os.getenv("LITELLM_BASE_URL"),
            os.getenv("OLLAMA_API_BASE"),
        ]
    )

    if not os.getenv("LLM_API_KEY"):
        missing_optional_vars.append("LLM_API_KEY")

    if not has_base_url:
        missing_optional_vars.append("LLM_API_BASE")

    if not os.getenv("PERPLEXITY_API_KEY"):
        missing_optional_vars.append("PERPLEXITY_API_KEY")

    if missing_required_vars:
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("MISSING REQUIRED ENVIRONMENT VARIABLES", style="bold red")
        error_text.append("\n\n", style="white")

        for var in missing_required_vars:
            error_text.append(f"• {var}", style="bold yellow")
            error_text.append(" is not set\n", style="white")

        if missing_optional_vars:
            error_text.append("\nOptional environment variables:\n", style="dim white")
            for var in missing_optional_vars:
                error_text.append(f"• {var}", style="dim yellow")
                error_text.append(" is not set\n", style="dim white")

        error_text.append("\nRequired environment variables:\n", style="white")
        for var in missing_required_vars:
            if var == "STRIX_LLM":
                error_text.append("• ", style="white")
                error_text.append("STRIX_LLM", style="bold cyan")
                error_text.append(
                    " - Model name to use with litellm (e.g., 'openai/gpt-5')\n",
                    style="white",
                )

        if missing_optional_vars:
            error_text.append("\nOptional environment variables:\n", style="white")
            for var in missing_optional_vars:
                if var == "LLM_API_KEY":
                    error_text.append("• ", style="white")
                    error_text.append("LLM_API_KEY", style="bold cyan")
                    error_text.append(
                        " - API key for the LLM provider "
                        "(not needed for local models, Vertex AI, AWS, etc.)\n",
                        style="white",
                    )
                elif var == "LLM_API_BASE":
                    error_text.append("• ", style="white")
                    error_text.append("LLM_API_BASE", style="bold cyan")
                    error_text.append(
                        " - Custom API base URL if using local models (e.g., Ollama, LMStudio)\n",
                        style="white",
                    )
                elif var == "PERPLEXITY_API_KEY":
                    error_text.append("• ", style="white")
                    error_text.append("PERPLEXITY_API_KEY", style="bold cyan")
                    error_text.append(
                        " - API key for Perplexity AI web search (enables real-time research)\n",
                        style="white",
                    )

        error_text.append("\n📍 GitHub Actions Tip:\n", style="bold cyan")
        error_text.append(
            "For GitHub Actions, use --roocode flag for free AI models,\n"
            "or add ROOCODE_ACCESS_TOKEN to your repository secrets.\n",
            style="white"
        )
        
        error_text.append("\nExample setup:\n", style="white")
        error_text.append("export STRIX_LLM='openai/gpt-5'\n", style="dim white")

        if missing_optional_vars:
            for var in missing_optional_vars:
                if var == "LLM_API_KEY":
                    error_text.append(
                        "export LLM_API_KEY='your-api-key-here'  "
                        "# not needed for local models, Vertex AI, AWS, etc.\n",
                        style="dim white",
                    )
                elif var == "LLM_API_BASE":
                    error_text.append(
                        "export LLM_API_BASE='http://localhost:11434'  "
                        "# needed for local models only\n",
                        style="dim white",
                    )
                elif var == "PERPLEXITY_API_KEY":
                    error_text.append(
                        "export PERPLEXITY_API_KEY='your-perplexity-key-here'\n", style="dim white"
                    )

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX CONFIGURATION ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )

        console.print("\n")
        console.print(panel)
        console.print()
        sys.exit(1)


def check_docker_installed() -> None:
    if shutil.which("docker") is None:
        console = Console()
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("DOCKER NOT INSTALLED", style="bold red")
        error_text.append("\n\n", style="white")
        error_text.append("The 'docker' CLI was not found in your PATH.\n", style="white")
        error_text.append(
            "Please install Docker and ensure the 'docker' command is available.\n\n", style="white"
        )
        
        if IS_GITHUB_ACTIONS:
            error_text.append("⚠️  Docker should be pre-installed on GitHub runners.\n", style="yellow")
            error_text.append("Try running: sudo systemctl start docker\n", style="dim white")

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX STARTUP ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )
        console.print("\n", panel, "\n")
        sys.exit(1)


async def warm_up_llm() -> None:
    console = Console()

    try:
        model_name = os.getenv("STRIX_LLM", "openai/gpt-5")
        api_key = os.getenv("LLM_API_KEY")
        api_base = (
            os.getenv("LLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("LITELLM_BASE_URL")
            or os.getenv("OLLAMA_API_BASE")
        )

        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Reply with just 'OK'."},
        ]

        llm_timeout = int(os.getenv("LLM_TIMEOUT", "600"))

        # Handle Qwen Code provider - convert qwencode/ prefix to proper LiteLLM format
        if model_name.startswith("qwencode/"):
            from strix.llm.qwencode_provider import configure_qwencode_for_litellm, is_qwencode_model
            try:
                model_name, api_key, api_base = configure_qwencode_for_litellm(model_name)
            except RuntimeError as e:
                # If not authenticated, skip warm-up (will be handled by dashboard auth)
                console.print(f"[dim yellow]⚠️  Qwen Code warm-up skipped: {e}[/]")
                return
        
        # Handle Roo Code provider - convert roocode/ prefix to proper LiteLLM format
        elif model_name.startswith("roocode/"):
            from strix.llm.roocode_provider import configure_roocode_for_litellm, is_roocode_model
            try:
                model_name, api_key, api_base = configure_roocode_for_litellm(model_name)
            except RuntimeError as e:
                # If not authenticated, skip warm-up (will be handled by dashboard auth)
                console.print(f"[dim yellow]⚠️  Roo Code warm-up skipped: {e}[/]")
                return

        completion_kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": test_messages,
            "timeout": llm_timeout,
        }
        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base

        response = litellm.completion(**completion_kwargs)

        validate_llm_response(response)

    except Exception as e:  # noqa: BLE001
        error_text = Text()
        error_text.append("❌ ", style="bold red")
        error_text.append("LLM CONNECTION FAILED", style="bold red")
        error_text.append("\n\n", style="white")
        error_text.append("Could not establish connection to the language model.\n", style="white")
        error_text.append("Please check your configuration and try again.\n", style="white")
        error_text.append(f"\nError: {e}", style="dim white")

        panel = Panel(
            error_text,
            title="[bold red]🛡️  STRIX STARTUP ERROR",
            title_align="center",
            border_style="red",
            padding=(1, 2),
        )

        console.print("\n")
        console.print(panel)
        console.print()
        sys.exit(1)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strix Multi-Agent Cybersecurity Penetration Testing Tool (GitHub Actions Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔═══════════════════════════════════════════════════════════════════════════╗
║                     🦉 STRIX - GITHUB ACTIONS EDITION                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  This tool is designed for GitHub Actions CI/CD workflows.                ║
║  The recommended way to use Strix is through the web dashboard.           ║
║                                                                           ║
║  GITHUB ACTIONS SETUP:                                                    ║
║  1. Go to your repository's Actions tab                                   ║
║  2. Run the "Strix Autonomous Dashboard" workflow                         ║
║  3. Click the Cloudflare tunnel URL in the workflow output                ║
║  4. Configure your scan in the web dashboard                              ║
║  5. Click "Configure and Fire" to start                                   ║
║                                                                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  LOCAL TESTING (for development):                                         ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  # Use Roo Code Cloud (free, recommended):                                ║
║  strix --roocode --target https://example.com                             ║
║                                                                           ║
║  # Use Qwen Code CLI (2,000 free requests/day):                           ║
║  strix --qwencode --target https://example.com                            ║
║                                                                           ║
║  # Multiple targets (white-box testing):                                  ║
║  strix --roocode --target ./my-repo --target https://example.com          ║
║                                                                           ║
║  # Enable root access for tool installation:                              ║
║  strix --roocode --root-access --target https://example.com               ║
║                                                                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║  DASHBOARD MODE (local):                                                  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  Start the dashboard locally:                                             ║
║  python -m strix.dashboard.server --port 8080                             ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
        """,
    )

    parser.add_argument(
        "-t",
        "--target",
        type=str,
        required=True,
        action="append",
        help="Target to test (URL, repository, local directory path, domain name, or IP address). "
        "Can be specified multiple times for multi-target scans.",
    )
    parser.add_argument(
        "--instruction",
        type=str,
        help="Custom instructions for the penetration test. This can be "
        "specific vulnerability types to focus on (e.g., 'Focus on IDOR and XSS'), "
        "testing approaches (e.g., 'Perform thorough authentication testing'), "
        "test credentials (e.g., 'Use the following credentials to access the app: "
        "admin:password123'), "
        "or areas of interest (e.g., 'Check login API endpoint for security issues').",
    )

    parser.add_argument(
        "--instruction-file",
        type=str,
        help="Path to a file containing detailed custom instructions for the penetration test. "
        "Use this option when you have lengthy or complex instructions saved in a file "
        "(e.g., '--instruction-file ./detailed_instructions.txt').",
    )

    parser.add_argument(
        "--run-name",
        type=str,
        help="Custom name for this penetration test run",
    )

    parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_true",
        default=IS_GITHUB_ACTIONS,  # Default to non-interactive in GitHub Actions
        help=(
            "Run in non-interactive mode (no TUI, exits on completion). "
            "Automatically enabled in GitHub Actions environment."
        ),
    )

    # Roo Code Cloud integration options
    roocode_group = parser.add_argument_group("Roo Code Cloud Options (Recommended)")
    roocode_group.add_argument(
        "--roocode",
        action="store_true",
        default=os.getenv("STRIX_USE_ROOCODE", "").lower() == "true",
        help=(
            "Use Roo Code Cloud for AI models (free, no API keys required). "
            "Automatically authenticates via browser OAuth or environment token."
        ),
    )
    roocode_group.add_argument(
        "--roocode-login",
        action="store_true",
        help="Authenticate with Roo Code Cloud and exit.",
    )
    roocode_group.add_argument(
        "--roocode-logout",
        action="store_true",
        help="Log out from Roo Code Cloud and exit.",
    )
    roocode_group.add_argument(
        "--roocode-model",
        type=str,
        choices=list(ROOCODE_MODELS.keys()) if ROOCODE_MODELS else None,
        default="grok-code-fast-1",
        help=(
            "Roo Code model to use. Options: "
            "grok-code-fast-1 (fast, 262k context), "
            "roo/code-supernova (advanced, multimodal). "
            "Default: grok-code-fast-1"
        ),
    )

    # Qwen Code CLI integration options
    qwencode_group = parser.add_argument_group("Qwen Code CLI Options")
    qwencode_group.add_argument(
        "--qwencode",
        action="store_true",
        default=os.getenv("STRIX_USE_QWENCODE", "").lower() == "true",
        help=(
            "Use Qwen Code CLI for AI models (2,000 free requests/day). "
            "Authenticates via browser OAuth with qwen.ai or uses API key."
        ),
    )
    qwencode_group.add_argument(
        "--qwencode-login",
        action="store_true",
        help="Authenticate with Qwen Code CLI and exit.",
    )
    qwencode_group.add_argument(
        "--qwencode-logout",
        action="store_true",
        help="Log out from Qwen Code CLI and exit.",
    )
    qwencode_group.add_argument(
        "--qwencode-model",
        type=str,
        choices=list(QWENCODE_MODELS.keys()) if QWENCODE_MODELS else None,
        default="qwen3-coder-plus",
        help=(
            "Qwen Code model to use. Options: "
            "qwen3-coder-plus (advanced), "
            "qwen3-coder (balanced). "
            "Default: qwen3-coder-plus"
        ),
    )

    # Root access options
    access_group = parser.add_argument_group("Access Control Options")
    access_group.add_argument(
        "--root-access",
        action="store_true",
        default=os.getenv("STRIX_ROOT_ACCESS", "").lower() == "true",
        help=(
            "Enable root access mode for unrestricted terminal commands. "
            "Allows the AI agent to install tools, modify system settings, "
            "and execute privileged commands within the sandboxed container."
        ),
    )
    access_group.add_argument(
        "--access-level",
        type=str,
        choices=["standard", "elevated", "root"],
        default=os.getenv("STRIX_ACCESS_LEVEL", "standard"),
        help=(
            "Set the access level for terminal commands. "
            "standard: Normal user access (default), "
            "elevated: Can use sudo for specific commands, "
            "root: Full unrestricted access."
        ),
    )

    # GitHub Actions specific options
    ga_group = parser.add_argument_group("GitHub Actions Options")
    ga_group.add_argument(
        "--github-actions",
        action="store_true",
        default=IS_GITHUB_ACTIONS,
        help="Explicitly enable GitHub Actions mode (auto-detected from environment).",
    )
    ga_group.add_argument(
        "--dashboard-mode",
        action="store_true",
        help="Start the web dashboard server instead of running a scan.",
    )
    ga_group.add_argument(
        "--dashboard-port",
        type=int,
        default=int(os.getenv("STRIX_DASHBOARD_PORT", "8080")),
        help="Port for the dashboard server (default: 8080).",
    )

    args = parser.parse_args()

    if args.instruction and args.instruction_file:
        parser.error("Cannot specify both --instruction and --instruction-file. Use one or the other.")

    if args.instruction_file:
        instruction_path = Path(args.instruction_file)
        try:
            with instruction_path.open(encoding="utf-8") as f:
                args.instruction = f.read().strip()
                if not args.instruction:
                    parser.error(f"Instruction file '{instruction_path}' is empty")
        except Exception as e:
            parser.error(f"Failed to read instruction file '{instruction_path}': {e}")

    args.targets_info = []
    for target in args.target:
        try:
            target_type, target_dict = infer_target_type(target)

            if target_type == "local_code":
                display_target = target_dict.get("target_path", target)
            else:
                display_target = target

            args.targets_info.append(
                {"type": target_type, "details": target_dict, "original": display_target}
            )
        except ValueError:
            parser.error(f"Invalid target '{target}'")

    assign_workspace_subdirs(args.targets_info)

    return args


def display_completion_message(args: argparse.Namespace, results_path: Path) -> None:
    console = Console()
    tracer = get_global_tracer()

    scan_completed = False
    if tracer and tracer.scan_results:
        scan_completed = tracer.scan_results.get("scan_completed", False)

    has_vulnerabilities = tracer and len(tracer.vulnerability_reports) > 0

    completion_text = Text()
    if scan_completed:
        completion_text.append("🦉 ", style="bold white")
        completion_text.append("AGENT FINISHED", style="bold green")
        completion_text.append(" • ", style="dim white")
        completion_text.append("Penetration test completed", style="white")
    else:
        completion_text.append("🦉 ", style="bold white")
        completion_text.append("SESSION ENDED", style="bold yellow")
        completion_text.append(" • ", style="dim white")
        completion_text.append("Penetration test interrupted by user", style="white")

    stats_text = build_final_stats_text(tracer)

    target_text = Text()
    if len(args.targets_info) == 1:
        target_text.append("🎯 Target: ", style="bold cyan")
        target_text.append(args.targets_info[0]["original"], style="bold white")
    else:
        target_text.append("🎯 Targets: ", style="bold cyan")
        target_text.append(f"{len(args.targets_info)} targets\n", style="bold white")
        for i, target_info in enumerate(args.targets_info):
            target_text.append("   • ", style="dim white")
            target_text.append(target_info["original"], style="white")
            if i < len(args.targets_info) - 1:
                target_text.append("\n")

    panel_parts = [completion_text, "\n\n", target_text]

    if stats_text.plain:
        panel_parts.extend(["\n", stats_text])

    if scan_completed or has_vulnerabilities:
        results_text = Text()
        results_text.append("📊 Results Saved To: ", style="bold cyan")
        results_text.append(str(results_path), style="bold yellow")
        panel_parts.extend(["\n\n", results_text])
        
    # Add GitHub Actions specific info
    if IS_GITHUB_ACTIONS:
        ga_text = Text()
        ga_text.append("\n\n📍 GitHub Actions: ", style="bold cyan")
        ga_text.append(f"Run {GITHUB_RUN_ID}", style="white")
        if GITHUB_REPOSITORY:
            ga_text.append(f" in {GITHUB_REPOSITORY}", style="dim white")
        panel_parts.append(ga_text)

    panel_content = Text.assemble(*panel_parts)

    border_style = "green" if scan_completed else "yellow"

    panel = Panel(
        panel_content,
        title="[bold green]🛡️  STRIX CYBERSECURITY AGENT",
        title_align="center",
        border_style=border_style,
        padding=(1, 2),
    )

    console.print("\n")
    console.print(panel)
    console.print()


def pull_docker_image() -> None:
    console = Console()
    client = check_docker_connection()

    if image_exists(client, STRIX_IMAGE):
        return

    console.print()
    console.print(f"[bold cyan]🐳 Pulling Docker image:[/] {STRIX_IMAGE}")
    console.print("[dim yellow]This only happens on first run and may take a few minutes...[/]")
    console.print()

    with console.status("[bold cyan]Downloading image layers...", spinner="dots") as status:
        try:
            layers_info: dict[str, str] = {}
            last_update = ""

            for line in client.api.pull(STRIX_IMAGE, stream=True, decode=True):
                last_update = process_pull_line(line, layers_info, status, last_update)

        except DockerException as e:
            console.print()
            error_text = Text()
            error_text.append("❌ ", style="bold red")
            error_text.append("FAILED TO PULL IMAGE", style="bold red")
            error_text.append("\n\n", style="white")
            error_text.append(f"Could not download: {STRIX_IMAGE}\n", style="white")
            error_text.append(str(e), style="dim red")

            panel = Panel(
                error_text,
                title="[bold red]🛡️  DOCKER PULL ERROR",
                title_align="center",
                border_style="red",
                padding=(1, 2),
            )
            console.print(panel, "\n")
            sys.exit(1)

    success_text = Text()
    success_text.append("✅ ", style="bold green")
    success_text.append("Successfully pulled Docker image", style="green")
    console.print(success_text)
    console.print()


def run_dashboard_server(port: int = 8080) -> None:
    """Start the web dashboard server."""
    from strix.dashboard.server import run_dashboard
    run_dashboard(host="0.0.0.0", port=port)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    args = parse_arguments()
    console = Console()
    
    # Display GitHub Actions notice
    if IS_GITHUB_ACTIONS:
        console.print()
        console.print("[bold cyan]🦉 STRIX - GitHub Actions Mode[/]")
        console.print(f"[dim]Repository: {GITHUB_REPOSITORY}[/]")
        console.print(f"[dim]Workflow: {GITHUB_WORKFLOW}[/]")
        console.print(f"[dim]Run ID: {GITHUB_RUN_ID}[/]")
        console.print()

    # Handle dashboard mode
    if args.dashboard_mode:
        console.print(f"\n[bold cyan]🌐 Starting Strix Dashboard on port {args.dashboard_port}...[/]\n")
        run_dashboard_server(args.dashboard_port)
        return

    # Handle Roo Code authentication commands
    if args.roocode_login:
        provider = get_roocode_provider()
        console.print("\n[bold cyan]🦉 Authenticating with Roo Code Cloud...[/]\n")
        if provider.login():
            console.print("[bold green]✅ Successfully logged in to Roo Code Cloud![/]")
            user_info = provider.get_user_info()
            if user_info and user_info.get("email"):
                console.print(f"   Logged in as: {user_info['email']}")
        else:
            console.print("[bold red]❌ Failed to log in to Roo Code Cloud[/]")
            sys.exit(1)
        sys.exit(0)

    if args.roocode_logout:
        provider = get_roocode_provider()
        provider.logout()
        console.print("[bold green]✅ Logged out from Roo Code Cloud[/]")
        sys.exit(0)

    # Handle Qwen Code CLI authentication commands
    if args.qwencode_login:
        provider = get_qwencode_provider()
        console.print("\n[bold cyan]🤖 Authenticating with Qwen Code CLI...[/]\n")
        if provider.login():
            console.print("[bold green]✅ Successfully logged in to Qwen Code CLI![/]")
            user_info = provider.get_user_info()
            if user_info and user_info.get("email"):
                console.print(f"   Logged in as: {user_info['email']}")
            console.print("   You have 2,000 free requests per day!")
        else:
            console.print("[bold red]❌ Failed to log in to Qwen Code CLI[/]")
            console.print("   Tip: Set QWENCODE_API_KEY environment variable for API key auth.")
            sys.exit(1)
        sys.exit(0)

    if args.qwencode_logout:
        provider = get_qwencode_provider()
        provider.logout()
        console.print("[bold green]✅ Logged out from Qwen Code CLI[/]")
        sys.exit(0)

    # Configure Roo Code if requested
    use_roocode = args.roocode or os.getenv("STRIX_USE_ROOCODE", "").lower() == "true"
    use_qwencode = args.qwencode or os.getenv("STRIX_USE_QWENCODE", "").lower() == "true"
    
    if use_roocode:
        os.environ["STRIX_USE_ROOCODE"] = "true"
        os.environ["STRIX_LLM"] = f"roocode/{args.roocode_model}"
        console.print(f"\n[bold cyan]🦉 Using Roo Code Cloud model: {args.roocode_model}[/]\n")
    elif use_qwencode:
        os.environ["STRIX_USE_QWENCODE"] = "true"
        os.environ["STRIX_LLM"] = f"qwencode/{args.qwencode_model}"
        console.print(f"\n[bold cyan]🤖 Using Qwen Code CLI model: {args.qwencode_model}[/]")
        console.print("   (2,000 free requests/day)\n")

    # Configure root access if requested
    if args.root_access or args.access_level == "root":
        os.environ["STRIX_ROOT_ACCESS"] = "true"
        os.environ["STRIX_ACCESS_LEVEL"] = "root"
        console.print("[bold yellow]⚠️  Root access enabled - unrestricted terminal commands[/]\n")
    elif args.access_level:
        os.environ["STRIX_ACCESS_LEVEL"] = args.access_level
        if args.access_level == "elevated":
            console.print("[bold cyan]🔧 Elevated access enabled - sudo available[/]\n")

    check_docker_installed()
    pull_docker_image()

    validate_environment(use_roocode=use_roocode, use_qwencode=use_qwencode)
    asyncio.run(warm_up_llm())

    if not args.run_name:
        args.run_name = generate_run_name(args.targets_info)
        if IS_GITHUB_ACTIONS and GITHUB_RUN_ID:
            args.run_name = f"github-{GITHUB_RUN_ID}-{args.run_name}"

    for target_info in args.targets_info:
        if target_info["type"] == "repository":
            repo_url = target_info["details"]["target_repo"]
            dest_name = target_info["details"].get("workspace_subdir")
            cloned_path = clone_repository(repo_url, args.run_name, dest_name)
            target_info["details"]["cloned_repo_path"] = cloned_path

    args.local_sources = collect_local_sources(args.targets_info)

    if args.non_interactive:
        asyncio.run(run_cli(args))
    else:
        asyncio.run(run_tui(args))

    results_path = Path("strix_runs") / args.run_name
    display_completion_message(args, results_path)

    if args.non_interactive:
        tracer = get_global_tracer()
        if tracer and tracer.vulnerability_reports:
            sys.exit(2)


if __name__ == "__main__":
    main()
