"""Renderer for Multi-Agent Collaboration tool results."""

from typing import Any

from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base_renderer import ToolRenderer


class CollaborationRenderer(ToolRenderer):
    """Renderer for collaboration and coordination tool results."""

    tool_names = [
        "claim_target",
        "release_claim",
        "list_claims",
        "share_finding",
        "list_findings",
        "get_finding_details",
        "add_to_work_queue",
        "get_next_work_item",
        "list_work_queue",
        "request_help",
        "respond_to_help_request",
        "list_help_requests",
        "get_collaboration_status",
        "broadcast_message",
    ]

    def render(self, result: dict[str, Any], console: Console) -> RenderableType | None:
        """Render collaboration tool results."""
        if not isinstance(result, dict):
            return None

        if not result.get("success", False) and "error" in result:
            error = result.get("error", "Unknown error")
            return Panel(
                Text(f"[red]Error:[/red] {error}", style="red"),
                title="[red]Collaboration Error[/red]",
                border_style="red",
            )

        tool_name = self._detect_tool_name(result)

        if tool_name == "claim_target":
            return self._render_claim_result(result)
        elif tool_name == "release_claim":
            return self._render_release_result(result)
        elif tool_name == "list_claims":
            return self._render_claims_list(result)
        elif tool_name == "share_finding":
            return self._render_share_finding(result)
        elif tool_name == "list_findings":
            return self._render_findings_list(result)
        elif tool_name == "get_finding_details":
            return self._render_finding_details(result)
        elif tool_name in ["add_to_work_queue", "get_next_work_item"]:
            return self._render_queue_action(result, tool_name)
        elif tool_name == "list_work_queue":
            return self._render_work_queue(result)
        elif tool_name == "request_help":
            return self._render_help_request(result)
        elif tool_name == "list_help_requests":
            return self._render_help_requests_list(result)
        elif tool_name == "get_collaboration_status":
            return self._render_status(result)
        elif tool_name == "broadcast_message":
            return self._render_broadcast(result)

        return None

    def _detect_tool_name(self, result: dict[str, Any]) -> str:
        """Detect which tool generated the result."""
        if "claim_id" in result and "claim_details" in result:
            return "claim_target"
        if "released_claim" in result:
            return "release_claim"
        if "claims" in result and "by_agent" in result:
            return "list_claims"
        if "finding_id" in result and "finding_summary" in result:
            return "share_finding"
        if "findings" in result and "chain_opportunities" in result:
            return "list_findings"
        if "finding" in result and "chain_suggestions" in result:
            return "get_finding_details"
        if "queue_id" in result or "work_item" in result:
            return "add_to_work_queue" if "queue_position" in result else "get_next_work_item"
        if "queue_items" in result:
            return "list_work_queue"
        if "request_id" in result and "broadcast_status" in result:
            return "request_help"
        if "requests" in result and "by_type" in result:
            return "list_help_requests"
        if "summary" in result and "my_activity" in result:
            return "get_collaboration_status"
        if "broadcast_id" in result:
            return "broadcast_message"
        return "unknown"

    def _severity_style(self, severity: str | None) -> str:
        """Get style for severity level."""
        if not severity:
            return "white"
        severity_styles = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "green",
            "info": "blue",
        }
        return severity_styles.get(severity.lower(), "white")

    def _render_claim_result(self, result: dict[str, Any]) -> Panel:
        """Render claim target result."""
        if result.get("success"):
            claim_details = result.get("claim_details", {})
            content = Text()
            content.append("✓ Claimed Successfully\n\n", style="green bold")
            content.append(f"Target: ", style="bold")
            content.append(f"{claim_details.get('target', 'N/A')}\n", style="cyan")
            content.append(f"Test Type: ", style="bold")
            content.append(f"{claim_details.get('test_type', 'N/A')}\n")
            content.append(f"Claim ID: ", style="bold")
            content.append(f"{result.get('claim_id', 'N/A')}\n", style="dim")
            content.append(f"Expires in: ", style="bold")
            content.append(f"{claim_details.get('expires_in_minutes', 30)} minutes\n")
            
            border_style = "green"
            title = "[bold green]🎯 Target Claimed[/bold green]"
        else:
            conflict = result.get("conflict", {})
            content = Text()
            content.append("✗ Claim Failed\n\n", style="red bold")
            content.append(f"Already claimed by: ", style="bold")
            content.append(f"{conflict.get('claimed_by', 'Unknown')}\n", style="yellow")
            content.append(f"Test Type: ", style="bold")
            content.append(f"{conflict.get('test_type', 'N/A')}\n")
            content.append(f"Time Remaining: ", style="bold")
            content.append(f"{conflict.get('time_remaining_minutes', 'N/A')} minutes\n")
            
            if result.get("suggestion"):
                content.append(f"\nSuggestion: {result['suggestion']}", style="dim")
            
            border_style = "yellow"
            title = "[bold yellow]⚠️ Target Already Claimed[/bold yellow]"

        return Panel(content, title=title, border_style=border_style)

    def _render_release_result(self, result: dict[str, Any]) -> Panel:
        """Render release claim result."""
        released = result.get("released_claim", {})
        content = Text()
        content.append("✓ Claim Released\n\n", style="green bold")
        content.append(f"Target: ", style="bold")
        content.append(f"{released.get('target', 'N/A')}\n", style="cyan")
        content.append(f"Test Type: ", style="bold")
        content.append(f"{released.get('test_type', 'N/A')}\n")
        if released.get("reason"):
            content.append(f"Reason: ", style="bold")
            content.append(f"{released['reason']}\n")

        return Panel(
            content,
            title="[bold green]🔓 Claim Released[/bold green]",
            border_style="green",
        )

    def _render_claims_list(self, result: dict[str, Any]) -> Panel:
        """Render list of claims."""
        claims = result.get("claims", [])
        
        if not claims:
            return Panel(
                Text("No active claims. Use claim_target() to claim a target.", style="dim"),
                title="[bold cyan]📋 Active Claims[/bold cyan]",
                border_style="cyan",
            )

        table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        
        table.add_column("Target", overflow="fold")
        table.add_column("Test Type", width=12)
        table.add_column("Agent", width=15)
        table.add_column("Time Left", width=10)
        table.add_column("Mine", width=6)

        for claim in claims[:20]:
            target = claim.get("target", "N/A")
            test_type = claim.get("test_type", "N/A")
            agent_name = claim.get("agent_name", "Unknown")
            
            elapsed = claim.get("elapsed_minutes", 0)
            duration = claim.get("estimated_duration_minutes", 30)
            remaining = max(0, duration - elapsed)
            time_left = f"{remaining:.0f}m"
            
            is_mine = "✓" if claim.get("is_mine") else ""
            mine_style = "green bold" if claim.get("is_mine") else ""
            
            is_expired = claim.get("is_expired", False)
            if is_expired:
                time_left = "Expired"
            
            table.add_row(
                target,
                test_type,
                agent_name,
                Text(time_left, style="red" if is_expired else "green"),
                Text(is_mine, style=mine_style),
            )

        summary = f"Active: {result.get('active_count', 0)} | Expired: {result.get('expired_count', 0)}"
        
        return Panel(
            table,
            title="[bold cyan]📋 Active Claims[/bold cyan]",
            subtitle=f"[dim]{summary}[/dim]",
            border_style="cyan",
        )

    def _render_share_finding(self, result: dict[str, Any]) -> Panel:
        """Render share finding result."""
        finding = result.get("finding_summary", {})
        content = Text()
        content.append("🔴 Finding Shared!\n\n", style="red bold")
        content.append(f"Title: ", style="bold")
        content.append(f"{finding.get('title', 'N/A')}\n", style="cyan")
        content.append(f"Type: ", style="bold")
        content.append(f"{finding.get('type', 'N/A')}\n")
        content.append(f"Severity: ", style="bold")
        severity = finding.get("severity", "unknown")
        content.append(f"{severity.upper()}\n", style=self._severity_style(severity))
        content.append(f"Finding ID: ", style="bold")
        content.append(f"{finding.get('id', 'N/A')}\n", style="dim")
        content.append(f"Chainable: ", style="bold")
        chainable = "Yes" if finding.get("chainable") else "No"
        content.append(f"{chainable}\n", style="green" if finding.get("chainable") else "dim")
        
        content.append(f"\nBroadcast: {result.get('broadcast_status', 'Unknown')}", style="dim")

        return Panel(
            content,
            title="[bold red]📢 Finding Shared[/bold red]",
            border_style="red",
        )

    def _render_findings_list(self, result: dict[str, Any]) -> Panel:
        """Render list of findings."""
        findings = result.get("findings", [])
        chain_opps = result.get("chain_opportunities", [])
        
        if not findings:
            return Panel(
                Text("No findings yet. Use share_finding() when you discover vulnerabilities.", style="dim"),
                title="[bold red]🔍 Shared Findings[/bold red]",
                border_style="red",
            )

        table = Table(
            show_header=True,
            header_style="bold red",
            expand=True,
        )
        
        table.add_column("ID", width=12)
        table.add_column("Title", overflow="fold")
        table.add_column("Type", width=10)
        table.add_column("Severity", width=10)
        table.add_column("Chain", width=6)

        for finding in findings[:20]:
            finding_id = finding.get("finding_id", "N/A")[:10]
            title = (finding.get("title", "N/A")[:40] + "...") if len(finding.get("title", "")) > 40 else finding.get("title", "N/A")
            finding_type = finding.get("finding_type", "N/A")
            severity = finding.get("severity", "unknown")
            chainable = "✓" if finding.get("chainable") else ""
            
            table.add_row(
                finding_id,
                title,
                finding_type,
                Text(severity, style=self._severity_style(severity)),
                Text(chainable, style="green bold"),
            )

        # Add chain opportunities section
        content = [table]
        if chain_opps:
            chain_text = Text("\n\n🔗 Chain Opportunities:\n", style="bold yellow")
            for opp in chain_opps[:3]:
                chain_text.append(f"  • {opp.get('chain_name', 'Unknown')}: {opp.get('description', '')[:50]}...\n", style="yellow")
            content.append(chain_text)

        from rich.console import Group
        
        summary = result.get("severity_summary", {})
        subtitle = f"Critical: {summary.get('critical', 0)} | High: {summary.get('high', 0)} | Medium: {summary.get('medium', 0)}"

        return Panel(
            Group(*content),
            title="[bold red]🔍 Shared Findings[/bold red]",
            subtitle=f"[dim]{subtitle}[/dim]",
            border_style="red",
        )

    def _render_finding_details(self, result: dict[str, Any]) -> Panel:
        """Render detailed finding information."""
        finding = result.get("finding", {})
        
        content = Text()
        content.append(f"Title: ", style="bold")
        content.append(f"{finding.get('title', 'N/A')}\n", style="cyan bold")
        
        severity = finding.get("severity", "unknown")
        content.append(f"Severity: ", style="bold")
        content.append(f"{severity.upper()}\n", style=self._severity_style(severity))
        
        content.append(f"Type: ", style="bold")
        content.append(f"{finding.get('finding_type', 'N/A')}\n")
        
        content.append(f"Target: ", style="bold")
        content.append(f"{finding.get('target', 'N/A')}\n")
        
        content.append(f"\nDescription:\n", style="bold underline")
        content.append(f"{finding.get('description', 'N/A')}\n")
        
        if finding.get("poc"):
            content.append(f"\nPoC:\n", style="bold underline")
            content.append(f"{finding['poc']}\n", style="green")
        
        if finding.get("chain_suggestions"):
            content.append(f"\nChain Suggestions:\n", style="bold underline")
            for suggestion in finding["chain_suggestions"]:
                content.append(f"  • {suggestion}\n", style="yellow")

        return Panel(
            content,
            title=f"[bold red]📄 Finding: {finding.get('finding_id', 'Unknown')}[/bold red]",
            border_style="red",
        )

    def _render_queue_action(self, result: dict[str, Any], tool_name: str) -> Panel:
        """Render work queue action result."""
        if tool_name == "add_to_work_queue":
            item = result.get("item_summary", {})
            content = Text()
            content.append("✓ Added to Queue\n\n", style="green bold")
            content.append(f"Target: ", style="bold")
            content.append(f"{item.get('target', 'N/A')}\n", style="cyan")
            content.append(f"Test Types: ", style="bold")
            content.append(f"{', '.join(item.get('test_types', []))}\n")
            content.append(f"Priority: ", style="bold")
            content.append(f"{item.get('priority', 'N/A')}\n")
            content.append(f"Position: ", style="bold")
            content.append(f"#{result.get('queue_position', 'N/A')}\n")
            
            title = "[bold blue]📥 Added to Work Queue[/bold blue]"
        else:
            work_item = result.get("work_item")
            if work_item:
                content = Text()
                content.append("📋 Next Work Item:\n\n", style="blue bold")
                content.append(f"Target: ", style="bold")
                content.append(f"{work_item.get('target', 'N/A')}\n", style="cyan")
                content.append(f"Test Types: ", style="bold")
                content.append(f"{', '.join(work_item.get('test_types', []))}\n")
                content.append(f"Priority: ", style="bold")
                content.append(f"{work_item.get('priority', 'N/A')}\n")
                if work_item.get("description"):
                    content.append(f"\nNotes: {work_item['description']}", style="dim")
            else:
                content = Text("No pending work items in queue.", style="dim")
            
            title = "[bold blue]📋 Work Item[/bold blue]"

        return Panel(content, title=title, border_style="blue")

    def _render_work_queue(self, result: dict[str, Any]) -> Panel:
        """Render work queue list."""
        items = result.get("queue_items", [])
        
        if not items:
            return Panel(
                Text("Work queue is empty. Use add_to_work_queue() to add targets.", style="dim"),
                title="[bold blue]📋 Work Queue[/bold blue]",
                border_style="blue",
            )

        table = Table(
            show_header=True,
            header_style="bold blue",
            expand=True,
        )
        
        table.add_column("Target", overflow="fold")
        table.add_column("Test Types", width=20)
        table.add_column("Priority", width=10)
        table.add_column("Status", width=10)

        priority_styles = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }

        for item in items[:20]:
            target = item.get("target", "N/A")
            test_types = ", ".join(item.get("test_types", []))[:20]
            priority = item.get("priority", "medium")
            status = item.get("status", "pending")
            
            table.add_row(
                target,
                test_types,
                Text(priority, style=priority_styles.get(priority, "white")),
                status,
            )

        by_status = result.get("by_status", {})
        subtitle = f"Pending: {by_status.get('pending', 0)} | Claimed: {by_status.get('claimed', 0)}"

        return Panel(
            table,
            title="[bold blue]📋 Work Queue[/bold blue]",
            subtitle=f"[dim]{subtitle}[/dim]",
            border_style="blue",
        )

    def _render_help_request(self, result: dict[str, Any]) -> Panel:
        """Render help request result."""
        content = Text()
        content.append("🆘 Help Request Created!\n\n", style="yellow bold")
        content.append(f"Request ID: ", style="bold")
        content.append(f"{result.get('request_id', 'N/A')}\n", style="dim")
        content.append(f"Status: ", style="bold")
        content.append(f"{result.get('broadcast_status', 'Unknown')}\n")
        
        return Panel(
            content,
            title="[bold yellow]🆘 Help Requested[/bold yellow]",
            border_style="yellow",
        )

    def _render_help_requests_list(self, result: dict[str, Any]) -> Panel:
        """Render list of help requests."""
        requests = result.get("requests", [])
        
        if not requests:
            return Panel(
                Text("No open help requests.", style="dim"),
                title="[bold yellow]🆘 Help Requests[/bold yellow]",
                border_style="yellow",
            )

        table = Table(
            show_header=True,
            header_style="bold yellow",
            expand=True,
        )
        
        table.add_column("ID", width=12)
        table.add_column("Title", overflow="fold")
        table.add_column("Type", width=12)
        table.add_column("Urgency", width=10)
        table.add_column("Resp.", width=6)

        urgency_styles = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }

        for req in requests[:15]:
            req_id = req.get("request_id", "N/A")[:10]
            title = (req.get("title", "N/A")[:35] + "...") if len(req.get("title", "")) > 35 else req.get("title", "N/A")
            help_type = req.get("help_type", "N/A")
            urgency = req.get("urgency", "medium")
            responses = str(req.get("response_count", 0))
            
            table.add_row(
                req_id,
                title,
                help_type,
                Text(urgency, style=urgency_styles.get(urgency, "white")),
                responses,
            )

        return Panel(
            table,
            title="[bold yellow]🆘 Help Requests[/bold yellow]",
            border_style="yellow",
        )

    def _render_status(self, result: dict[str, Any]) -> Panel:
        """Render collaboration status overview."""
        summary = result.get("summary", {})
        recommendations = result.get("recommendations", [])
        
        content = Text()
        content.append("📊 Collaboration Status\n\n", style="bold")
        
        # Summary stats
        content.append("Claims: ", style="bold")
        content.append(f"{summary.get('active_claims', 0)} active")
        content.append(f" ({summary.get('my_claims', 0)} mine)\n")
        
        content.append("Findings: ", style="bold")
        content.append(f"{summary.get('total_findings', 0)} total")
        critical = summary.get('critical_findings', 0)
        if critical > 0:
            content.append(f" ({critical} critical)", style="red")
        content.append("\n")
        
        content.append("Work Queue: ", style="bold")
        content.append(f"{summary.get('pending_work_items', 0)} pending\n")
        
        content.append("Help Requests: ", style="bold")
        content.append(f"{summary.get('open_help_requests', 0)} open\n")
        
        # Chain opportunities
        chain_opps = result.get("chain_opportunities", [])
        if chain_opps:
            content.append("\n🔗 Chain Opportunities:\n", style="bold yellow")
            for opp in chain_opps[:3]:
                content.append(f"  • {opp.get('chain_name', 'Unknown')}\n", style="yellow")
        
        # Recommendations
        if recommendations:
            content.append("\n💡 Recommendations:\n", style="bold cyan")
            for rec in recommendations[:3]:
                content.append(f"  • {rec}\n", style="cyan")

        return Panel(
            content,
            title="[bold magenta]🤝 Collaboration Status[/bold magenta]",
            border_style="magenta",
        )

    def _render_broadcast(self, result: dict[str, Any]) -> Panel:
        """Render broadcast message result."""
        content = Text()
        content.append("📢 Message Broadcast!\n\n", style="green bold")
        content.append(f"Broadcast ID: ", style="bold")
        content.append(f"{result.get('broadcast_id', 'N/A')}\n", style="dim")
        content.append(f"Recipients: ", style="bold")
        recipients = result.get("recipients", "all agents")
        content.append(f"{recipients}\n")

        return Panel(
            content,
            title="[bold green]📢 Broadcast Sent[/bold green]",
            border_style="green",
        )
