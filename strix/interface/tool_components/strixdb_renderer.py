"""
StrixDB Renderer - Rich TUI rendering for StrixDB operations.
"""

from typing import Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .base_renderer import BaseRenderer


class StrixDBSaveRenderer(BaseRenderer):
    """Renderer for strixdb_save results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render save operation result."""
        console = console or Console()

        if result.get("success"):
            item = result.get("item", {})
            
            content = Text()
            content.append("✅ ", style="bold green")
            content.append("Saved to StrixDB\n\n", style="bold green")
            content.append("Name: ", style="dim")
            content.append(f"{item.get('name', 'unknown')}\n", style="bold white")
            content.append("Category: ", style="dim")
            content.append(f"{item.get('category', 'unknown')}\n", style="bold cyan")
            content.append("Path: ", style="dim")
            content.append(f"{item.get('path', 'unknown')}\n", style="white")
            
            if item.get("tags"):
                content.append("Tags: ", style="dim")
                content.append(", ".join(item["tags"]), style="bold yellow")

            panel = Panel(
                content,
                title="[bold green]📦 StrixDB Save",
                border_style="green",
            )
            console.print(panel)
        else:
            error = result.get("error", "Unknown error")
            content = Text()
            content.append("❌ ", style="bold red")
            content.append("Save Failed\n\n", style="bold red")
            content.append(error, style="red")

            panel = Panel(
                content,
                title="[bold red]📦 StrixDB Error",
                border_style="red",
            )
            console.print(panel)


class StrixDBSearchRenderer(BaseRenderer):
    """Renderer for strixdb_search results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render search results."""
        console = console or Console()

        if result.get("success"):
            results = result.get("results", [])
            total = result.get("total_count", len(results))
            query = result.get("query", "")

            if not results:
                content = Text()
                content.append("🔍 ", style="bold yellow")
                content.append(f"No results found for: ", style="white")
                content.append(query, style="bold yellow")

                panel = Panel(
                    content,
                    title="[bold yellow]📦 StrixDB Search",
                    border_style="yellow",
                )
                console.print(panel)
                return

            table = Table(
                title=f"Search Results ({len(results)} of {total})",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Name", style="white")
            table.add_column("Category", style="cyan")
            table.add_column("Path", style="dim")

            for item in results:
                table.add_row(
                    item.get("name", "unknown"),
                    item.get("category", "unknown"),
                    item.get("path", ""),
                )

            panel = Panel(
                table,
                title=f"[bold cyan]🔍 StrixDB Search: {query}",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Search failed")
            console.print(f"[red]❌ Search Error: {error}[/red]")


class StrixDBGetRenderer(BaseRenderer):
    """Renderer for strixdb_get results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render get result."""
        console = console or Console()

        if result.get("success"):
            item = result.get("item", {})
            metadata = item.get("metadata", {})

            content = Text()
            content.append("📄 ", style="bold blue")
            content.append(f"{item.get('name', 'unknown')}\n\n", style="bold white")
            
            content.append("Category: ", style="dim")
            content.append(f"{item.get('category', 'unknown')}\n", style="cyan")
            
            if metadata.get("description"):
                content.append("Description: ", style="dim")
                content.append(f"{metadata['description']}\n", style="white")
            
            if metadata.get("tags"):
                content.append("Tags: ", style="dim")
                content.append(f"{', '.join(metadata['tags'])}\n", style="yellow")
            
            content.append("\n--- Content ---\n", style="dim")
            
            item_content = item.get("content", "")
            if len(item_content) > 2000:
                content.append(f"{item_content[:2000]}...\n", style="white")
                content.append(f"(truncated, total {len(item_content)} characters)", style="dim")
            else:
                content.append(item_content, style="white")

            panel = Panel(
                content,
                title="[bold blue]📦 StrixDB Item",
                border_style="blue",
            )
            console.print(panel)
        else:
            error = result.get("error", "Item not found")
            console.print(f"[red]❌ Get Error: {error}[/red]")


class StrixDBListRenderer(BaseRenderer):
    """Renderer for strixdb_list results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render list results."""
        console = console or Console()

        if result.get("success"):
            items = result.get("items", [])
            total = result.get("total", len(items))

            if not items:
                console.print("[yellow]📦 StrixDB is empty[/yellow]")
                return

            # Group by category
            by_category: dict[str, list[dict[str, Any]]] = {}
            for item in items:
                cat = item.get("category", "unknown")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(item)

            tree = Tree("📦 [bold]StrixDB Contents[/bold]")

            for category, cat_items in sorted(by_category.items()):
                branch = tree.add(f"📁 [cyan]{category}[/cyan] ({len(cat_items)} items)")
                for item in cat_items[:10]:  # Show max 10 per category
                    branch.add(f"📄 [white]{item.get('name', 'unknown')}[/white]")
                if len(cat_items) > 10:
                    branch.add(f"[dim]... and {len(cat_items) - 10} more[/dim]")

            panel = Panel(
                tree,
                title=f"[bold cyan]📦 StrixDB ({total} items)",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "List failed")
            console.print(f"[red]❌ List Error: {error}[/red]")


class StrixDBDeleteRenderer(BaseRenderer):
    """Renderer for strixdb_delete results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render delete result."""
        console = console or Console()

        if result.get("success"):
            message = result.get("message", "Item deleted")
            console.print(f"[green]🗑️ {message}[/green]")
        else:
            error = result.get("error", "Delete failed")
            console.print(f"[red]❌ Delete Error: {error}[/red]")


class StrixDBCategoriesRenderer(BaseRenderer):
    """Renderer for strixdb_get_categories results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render categories."""
        console = console or Console()

        if result.get("success"):
            categories = result.get("categories", [])

            table = Table(
                title="StrixDB Categories",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Category", style="cyan")
            table.add_column("Description", style="white")
            table.add_column("Items", style="yellow", justify="right")

            for cat in categories:
                table.add_row(
                    cat.get("name", ""),
                    cat.get("description", ""),
                    str(cat.get("item_count", 0)),
                )

            panel = Panel(
                table,
                title="[bold cyan]📁 StrixDB Categories",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to get categories")
            console.print(f"[red]❌ Error: {error}[/red]")


class StrixDBStatsRenderer(BaseRenderer):
    """Renderer for strixdb_get_stats results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render stats."""
        console = console or Console()

        if result.get("success"):
            stats = result.get("stats", {})

            content = Text()
            content.append("📊 StrixDB Statistics\n\n", style="bold cyan")
            
            content.append("Repository: ", style="dim")
            content.append(f"{stats.get('repo_name', 'unknown')}\n", style="white")
            
            content.append("Branch: ", style="dim")
            content.append(f"{stats.get('branch', 'main')}\n", style="white")
            
            content.append("Total Items: ", style="dim")
            content.append(f"{stats.get('total_items', 0)}\n", style="bold green")
            
            content.append("Size: ", style="dim")
            content.append(f"{stats.get('size_kb', 0)} KB\n", style="white")
            
            content.append("Visibility: ", style="dim")
            content.append(f"{stats.get('visibility', 'unknown')}\n", style="white")
            
            if stats.get("last_updated"):
                content.append("Last Updated: ", style="dim")
                content.append(f"{stats['last_updated']}\n", style="white")
            
            content.append("\n📁 Items by Category:\n", style="bold")
            categories = stats.get("categories", {})
            for cat, count in sorted(categories.items()):
                if count > 0:
                    content.append(f"  {cat}: ", style="dim")
                    content.append(f"{count}\n", style="cyan")

            panel = Panel(
                content,
                title="[bold cyan]📦 StrixDB Stats",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to get stats")
            console.print(f"[red]❌ Stats Error: {error}[/red]")


class StrixDBRecentRenderer(BaseRenderer):
    """Renderer for strixdb_get_recent results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        """Render recent items."""
        console = console or Console()

        if result.get("success"):
            items = result.get("items", [])

            if not items:
                console.print("[yellow]📦 No recent items found[/yellow]")
                return

            table = Table(
                title="Recent StrixDB Activity",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Name", style="white")
            table.add_column("Category", style="cyan")
            table.add_column("Action", style="yellow")
            table.add_column("Time", style="dim")

            for item in items:
                action = item.get("action", "unknown")
                action_style = "green" if action == "added" else "yellow"
                
                table.add_row(
                    item.get("name", "unknown"),
                    item.get("category", "unknown"),
                    f"[{action_style}]{action}[/{action_style}]",
                    item.get("timestamp", "")[:10] if item.get("timestamp") else "",
                )

            panel = Panel(
                table,
                title="[bold cyan]🕒 Recent StrixDB Activity",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to get recent items")
            console.print(f"[red]❌ Error: {error}[/red]")


# ==============================================================================
# TARGET TRACKING RENDERERS
# ==============================================================================


class StrixDBTargetInitRenderer(BaseRenderer):
    """Renderer for strixdb_target_init results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            target = result.get("target", {})
            is_new = result.get("is_new", True)
            
            content = Text()
            
            if is_new:
                content.append("🎯 ", style="bold green")
                content.append("New Target Initialized\n\n", style="bold green")
            else:
                content.append("🎯 ", style="bold yellow")
                content.append("Existing Target Found\n\n", style="bold yellow")
            
            content.append("Target: ", style="dim")
            content.append(f"{target.get('slug', 'unknown')}\n", style="bold white")
            
            if not is_new:
                content.append("Previous Sessions: ", style="dim")
                content.append(f"{target.get('previous_sessions_count', 0)}\n", style="cyan")
                
                stats = target.get("stats", {})
                if stats.get("total_findings"):
                    content.append("Total Findings: ", style="dim")
                    content.append(f"{stats.get('total_findings', 0)} ", style="bold")
                    content.append(f"(C:{stats.get('critical', 0)} H:{stats.get('high', 0)} M:{stats.get('medium', 0)})\n", style="yellow")
            
            if result.get("next_step"):
                content.append("\n💡 ", style="cyan")
                content.append(result.get("next_step", ""), style="dim")

            color = "green" if is_new else "yellow"
            panel = Panel(
                content,
                title=f"[bold {color}]🎯 Target Tracking",
                border_style=color,
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to initialize target")
            console.print(f"[red]❌ Target Init Error: {error}[/red]")


class StrixDBTargetSessionStartRenderer(BaseRenderer):
    """Renderer for strixdb_target_session_start results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            session = result.get("session", {})
            summary = result.get("target_summary", {})
            previous = result.get("previous_work", {})
            pending = result.get("pending_work", {})
            recommendations = result.get("recommendations", [])
            
            content = Text()
            content.append("🚀 ", style="bold green")
            content.append("Session Started\n\n", style="bold green")
            
            content.append("Session ID: ", style="dim")
            content.append(f"{session.get('session_id', 'unknown')}\n", style="bold white")
            
            content.append("Target: ", style="dim")
            content.append(f"{session.get('target_slug', 'unknown')}\n", style="cyan")
            
            if session.get("objective"):
                content.append("Objective: ", style="dim")
                content.append(f"{session.get('objective')}\n", style="white")
            
            # Previous work summary
            if summary.get("previous_sessions", 0) > 0:
                content.append("\n📊 Previous Work:\n", style="bold yellow")
                content.append(f"  • Sessions: {summary.get('previous_sessions')}\n", style="dim")
                content.append(f"  • Findings: {summary.get('total_findings', 0)}\n", style="dim")
                content.append(f"  • Endpoints: {summary.get('endpoints_discovered', 0)}\n", style="dim")
                
                if previous.get("tested_vulnerability_types"):
                    content.append(f"  • Tested: {', '.join(previous['tested_vulnerability_types'][:5])}\n", style="dim")
            
            # Pending work
            if pending.get("high_priority"):
                content.append("\n⚡ High Priority:\n", style="bold red")
                for item in pending["high_priority"][:3]:
                    content.append(f"  • {item}\n", style="red")
            
            # Recommendations
            if recommendations:
                content.append("\n💡 Recommendations:\n", style="bold cyan")
                for rec in recommendations[:3]:
                    content.append(f"  • {rec}\n", style="cyan")

            panel = Panel(
                content,
                title="[bold green]🎯 Session Started",
                border_style="green",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to start session")
            console.print(f"[red]❌ Session Start Error: {error}[/red]")


class StrixDBTargetSessionEndRenderer(BaseRenderer):
    """Renderer for strixdb_target_session_end results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            summary = result.get("session_summary", {})
            continuation = result.get("continuation_saved", {})
            
            content = Text()
            content.append("✅ ", style="bold green")
            content.append("Session Ended\n\n", style="bold green")
            
            content.append("Session: ", style="dim")
            content.append(f"{summary.get('session_id', 'unknown')}\n", style="white")
            
            content.append("Duration: ", style="dim")
            content.append(f"{summary.get('duration_minutes', 0)} minutes\n", style="cyan")
            
            content.append("Findings: ", style="dim")
            content.append(f"{summary.get('findings_recorded', 0)}\n", style="bold yellow")
            
            content.append("Endpoints: ", style="dim")
            content.append(f"{summary.get('endpoints_discovered', 0)}\n", style="white")
            
            if continuation.get("immediate_follow_ups"):
                content.append("\n📌 Saved for Next Session:\n", style="bold cyan")
                for item in continuation["immediate_follow_ups"][:3]:
                    content.append(f"  • {item}\n", style="cyan")

            panel = Panel(
                content,
                title="[bold green]🎯 Session Complete",
                border_style="green",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to end session")
            console.print(f"[red]❌ Session End Error: {error}[/red]")


class StrixDBTargetFindingRenderer(BaseRenderer):
    """Renderer for strixdb_target_add_finding results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            finding = result.get("finding", {})
            severity = finding.get("severity", "info").lower()
            
            severity_colors = {
                "critical": "red",
                "high": "red",
                "medium": "yellow",
                "low": "cyan",
                "info": "blue",
            }
            color = severity_colors.get(severity, "white")
            
            content = Text()
            content.append("🐛 ", style=f"bold {color}")
            content.append("Finding Recorded\n\n", style=f"bold {color}")
            
            content.append("Title: ", style="dim")
            content.append(f"{finding.get('title', 'unknown')}\n", style="bold white")
            
            content.append("Severity: ", style="dim")
            content.append(f"{severity.upper()}\n", style=f"bold {color}")
            
            content.append("Type: ", style="dim")
            content.append(f"{finding.get('vulnerability_type', 'unknown')}\n", style="white")

            panel = Panel(
                content,
                title=f"[bold {color}]🎯 Finding Added",
                border_style=color,
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to add finding")
            console.print(f"[red]❌ Finding Error: {error}[/red]")


class StrixDBTargetListRenderer(BaseRenderer):
    """Renderer for strixdb_target_list results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            targets = result.get("targets", [])
            
            if not targets:
                console.print("[yellow]🎯 No targets found[/yellow]")
                return

            table = Table(
                title="Tracked Targets",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Target", style="white")
            table.add_column("Type", style="cyan")
            table.add_column("Sessions", style="yellow", justify="right")
            table.add_column("Findings", style="red", justify="right")
            table.add_column("Status", style="green")

            for t in targets:
                stats = t.get("stats", {})
                table.add_row(
                    t.get("slug", "unknown"),
                    t.get("target_type", "unknown"),
                    str(t.get("total_sessions", 0)),
                    str(stats.get("total_findings", 0)),
                    t.get("status", "unknown"),
                )

            panel = Panel(
                table,
                title="[bold cyan]🎯 StrixDB Targets",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to list targets")
            console.print(f"[red]❌ List Targets Error: {error}[/red]")


# ==============================================================================
# REPOSITORY EXTRACTION RENDERERS
# ==============================================================================


class StrixDBRepoExtractInitRenderer(BaseRenderer):
    """Renderer for strixdb_repo_extract_init results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            is_new = result.get("is_new", True)
            stats = result.get("stats", {})
            
            content = Text()
            
            if is_new:
                content.append("📦 ", style="bold green")
                content.append("Repository Initialized\n\n", style="bold green")
            else:
                content.append("📦 ", style="bold yellow")
                content.append("Repository Already Exists\n\n", style="bold yellow")
            
            content.append("Slug: ", style="dim")
            content.append(f"{result.get('repo_slug', 'unknown')}\n", style="bold white")
            
            if is_new:
                content.append("Total Files: ", style="dim")
                content.append(f"{stats.get('total_files', 0)}\n", style="cyan")
                
                content.append("Size: ", style="dim")
                content.append(f"{stats.get('total_size_mb', 0)} MB\n", style="white")
                
                content.append("\n📁 Categories Found:\n", style="bold")
                categories = stats.get("categories", {})
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:8]:
                    if count > 0:
                        content.append(f"  • {cat}: {count}\n", style="dim")
            
            if result.get("next_steps"):
                content.append("\n💡 ", style="cyan")
                content.append(result.get("next_steps", "")[:200], style="dim")

            color = "green" if is_new else "yellow"
            panel = Panel(
                content,
                title=f"[bold {color}]📚 Repository Extraction",
                border_style=color,
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to initialize extraction")
            console.print(f"[red]❌ Extraction Init Error: {error}[/red]")


class StrixDBRepoExtractCategoryRenderer(BaseRenderer):
    """Renderer for strixdb_repo_extract_category results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            content = Text()
            content.append("📤 ", style="bold green")
            content.append("Category Extraction Complete\n\n", style="bold green")
            
            content.append("Category: ", style="dim")
            content.append(f"{result.get('category', 'unknown')}\n", style="bold cyan")
            
            content.append("Extracted: ", style="dim")
            content.append(f"{result.get('extracted_count', 0)} files\n", style="green")
            
            if result.get("failed_count", 0) > 0:
                content.append("Failed: ", style="dim")
                content.append(f"{result.get('failed_count', 0)} files\n", style="red")
            
            extracted = result.get("extracted_files", [])
            if extracted:
                content.append("\n📄 Extracted Files:\n", style="bold")
                for f in extracted[:5]:
                    content.append(f"  • {f}\n", style="dim")
                if len(extracted) > 5:
                    content.append(f"  ... and {len(extracted) - 5} more\n", style="dim")

            panel = Panel(
                content,
                title="[bold green]📚 Category Extracted",
                border_style="green",
            )
            console.print(panel)
        else:
            error = result.get("error", "Extraction failed")
            console.print(f"[red]❌ Category Extraction Error: {error}[/red]")


class StrixDBRepoExtractAllRenderer(BaseRenderer):
    """Renderer for strixdb_repo_extract_all results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            content = Text()
            content.append("✅ ", style="bold green")
            content.append("Full Extraction Complete\n\n", style="bold green")
            
            content.append("Total Extracted: ", style="dim")
            content.append(f"{result.get('total_extracted', 0)} files\n", style="bold green")
            
            if result.get("total_failed", 0) > 0:
                content.append("Failed: ", style="dim")
                content.append(f"{result.get('total_failed', 0)} files\n", style="red")
            
            by_category = result.get("by_category", {})
            if by_category:
                content.append("\n📁 By Category:\n", style="bold")
                for cat, data in sorted(by_category.items()):
                    extracted = data.get("extracted", 0)
                    if extracted > 0:
                        content.append(f"  • {cat}: {extracted}\n", style="cyan")

            panel = Panel(
                content,
                title="[bold green]📚 Full Extraction Complete",
                border_style="green",
            )
            console.print(panel)
        else:
            error = result.get("error", "Full extraction failed")
            console.print(f"[red]❌ Full Extraction Error: {error}[/red]")


class StrixDBRepoStatusRenderer(BaseRenderer):
    """Renderer for strixdb_repo_extract_status results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            stats = result.get("stats", {})
            
            content = Text()
            content.append("📊 ", style="bold cyan")
            content.append("Extraction Status\n\n", style="bold cyan")
            
            content.append("Repository: ", style="dim")
            content.append(f"{result.get('repo_slug', 'unknown')}\n", style="bold white")
            
            content.append("Status: ", style="dim")
            content.append(f"{result.get('status', 'unknown')}\n", style="green")
            
            content.append("Progress: ", style="dim")
            content.append(f"{stats.get('extracted', 0)}/{stats.get('total_files', 0)} ", style="cyan")
            content.append(f"({stats.get('extraction_percentage', 0)}%)\n", style="dim")
            
            pending = result.get("pending_by_category", {})
            if pending:
                content.append("\n📌 Pending by Category:\n", style="bold yellow")
                for cat, count in sorted(pending.items(), key=lambda x: x[1], reverse=True)[:5]:
                    content.append(f"  • {cat}: {count}\n", style="dim")

            panel = Panel(
                content,
                title="[bold cyan]📚 Extraction Status",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to get status")
            console.print(f"[red]❌ Status Error: {error}[/red]")


class StrixDBRepoListRenderer(BaseRenderer):
    """Renderer for strixdb_repo_list results."""

    def render(self, result: dict[str, Any], console: Console | None = None) -> None:
        console = console or Console()

        if result.get("success"):
            repos = result.get("repositories", [])
            
            if not repos:
                console.print("[yellow]📚 No extracted repositories found[/yellow]")
                return

            table = Table(
                title="Extracted Repositories",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Repository", style="white")
            table.add_column("Files", style="cyan", justify="right")
            table.add_column("Status", style="green")
            table.add_column("Tags", style="yellow")

            for repo in repos:
                table.add_row(
                    repo.get("slug", "unknown"),
                    str(repo.get("files_extracted", 0)),
                    repo.get("status", "unknown"),
                    ", ".join(repo.get("tags", [])[:3]),
                )

            panel = Panel(
                table,
                title="[bold cyan]📚 Extracted Repositories",
                border_style="cyan",
            )
            console.print(panel)
        else:
            error = result.get("error", "Failed to list repos")
            console.print(f"[red]❌ List Repos Error: {error}[/red]")


# Mapping of tool names to renderers
STRIXDB_RENDERERS = {
    # Original StrixDB
    "strixdb_save": StrixDBSaveRenderer,
    "strixdb_search": StrixDBSearchRenderer,
    "strixdb_get": StrixDBGetRenderer,
    "strixdb_list": StrixDBListRenderer,
    "strixdb_update": StrixDBSaveRenderer,
    "strixdb_delete": StrixDBDeleteRenderer,
    "strixdb_get_categories": StrixDBCategoriesRenderer,
    "strixdb_get_stats": StrixDBStatsRenderer,
    "strixdb_get_recent": StrixDBRecentRenderer,
    
    # Target Tracking
    "strixdb_target_init": StrixDBTargetInitRenderer,
    "strixdb_target_session_start": StrixDBTargetSessionStartRenderer,
    "strixdb_target_session_end": StrixDBTargetSessionEndRenderer,
    "strixdb_target_add_finding": StrixDBTargetFindingRenderer,
    "strixdb_target_add_endpoint": StrixDBSaveRenderer,  # Simple confirmation
    "strixdb_target_add_note": StrixDBSaveRenderer,
    "strixdb_target_add_technology": StrixDBSaveRenderer,
    "strixdb_target_update_progress": StrixDBSaveRenderer,
    "strixdb_target_get": StrixDBGetRenderer,
    "strixdb_target_list": StrixDBTargetListRenderer,
    
    # Repository Extraction
    "strixdb_repo_extract_init": StrixDBRepoExtractInitRenderer,
    "strixdb_repo_extract_file": StrixDBSaveRenderer,
    "strixdb_repo_extract_category": StrixDBRepoExtractCategoryRenderer,
    "strixdb_repo_extract_all": StrixDBRepoExtractAllRenderer,
    "strixdb_repo_extract_status": StrixDBRepoStatusRenderer,
    "strixdb_repo_list_extracted": StrixDBListRenderer,
    "strixdb_repo_get_item": StrixDBGetRenderer,
    "strixdb_repo_search": StrixDBSearchRenderer,
    "strixdb_repo_list": StrixDBRepoListRenderer,
}


def get_strixdb_renderer(tool_name: str) -> type[BaseRenderer] | None:
    """Get the appropriate renderer for a StrixDB tool."""
    return STRIXDB_RENDERERS.get(tool_name)
