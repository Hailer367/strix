"""Renderer for CVE/Exploit Database tool results."""

from typing import Any

from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base_renderer import ToolRenderer


class CVEDatabaseRenderer(ToolRenderer):
    """Renderer for CVE database and exploit search results."""

    tool_names = [
        "query_cve_database",
        "search_exploits",
        "get_cve_details",
        "search_github_advisories",
        "get_technology_vulnerabilities",
        "search_packetstorm",
    ]

    def render(self, result: dict[str, Any], console: Console) -> RenderableType | None:
        """Render CVE database results."""
        if not isinstance(result, dict):
            return None

        if not result.get("success", False):
            error = result.get("error", "Unknown error")
            return Panel(
                Text(f"[red]Error:[/red] {error}", style="red"),
                title="[red]CVE Query Failed[/red]",
                border_style="red",
            )

        tool_name = self._detect_tool_name(result)

        if tool_name == "query_cve_database":
            return self._render_cve_results(result)
        elif tool_name == "search_exploits":
            return self._render_exploit_results(result)
        elif tool_name == "get_cve_details":
            return self._render_cve_details(result)
        elif tool_name == "search_github_advisories":
            return self._render_github_advisories(result)
        elif tool_name == "get_technology_vulnerabilities":
            return self._render_tech_vulns(result)
        elif tool_name == "search_packetstorm":
            return self._render_packetstorm(result)

        return None

    def _detect_tool_name(self, result: dict[str, Any]) -> str:
        """Detect which tool generated the result."""
        if "cves" in result and "query_info" in result:
            return "query_cve_database"
        if "exploits" in result:
            return "search_exploits"
        if "cve_details" in result:
            return "get_cve_details"
        if "advisories" in result:
            return "search_github_advisories"
        if "vulnerabilities" in result and "testing_priority" in result:
            return "get_technology_vulnerabilities"
        if "direct_search_url" in result:
            return "search_packetstorm"
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

    def _render_cve_results(self, result: dict[str, Any]) -> Panel:
        """Render CVE database query results."""
        cves = result.get("cves", [])
        query_info = result.get("query_info", {})
        
        table = Table(
            title=f"CVEs for {query_info.get('keyword', 'Unknown')}",
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        
        table.add_column("CVE ID", style="cyan", width=18)
        table.add_column("Severity", width=10)
        table.add_column("Score", width=6)
        table.add_column("Exploit", width=8)
        table.add_column("Description", overflow="fold")

        for cve in cves[:15]:  # Limit display
            cve_id = cve.get("cve_id", "N/A")
            severity = cve.get("severity_level", "Unknown")
            score = cve.get("cvss_score")
            score_str = f"{score:.1f}" if score else "N/A"
            has_exploit = "Yes" if cve.get("has_known_exploit") else "No"
            exploit_style = "green bold" if cve.get("has_known_exploit") else "dim"
            description = (cve.get("description", "")[:80] + "...") if cve.get("description") else "N/A"
            
            table.add_row(
                cve_id,
                Text(severity, style=self._severity_style(severity)),
                score_str,
                Text(has_exploit, style=exploit_style),
                description,
            )

        summary = f"Found {len(cves)} CVEs"
        if query_info.get("version"):
            summary += f" for version {query_info['version']}"

        return Panel(
            table,
            title=f"[bold cyan] CVE Database Results - {summary}[/bold cyan]",
            border_style="cyan",
        )

    def _render_exploit_results(self, result: dict[str, Any]) -> Panel:
        """Render exploit search results."""
        exploits = result.get("exploits", [])
        search_info = result.get("search_info", {})

        table = Table(
            show_header=True,
            header_style="bold red",
            expand=True,
        )
        
        table.add_column("ID", style="red", width=15)
        table.add_column("Title", overflow="fold")
        table.add_column("Source", width=10)

        for exploit in exploits[:15]:
            exploit_id = exploit.get("exploit_id", "N/A")
            title = exploit.get("title", "N/A")[:60]
            source = exploit.get("source", "exploit-db")
            
            table.add_row(exploit_id, title, source)

        alt_searches = result.get("alternative_searches", [])
        footer = ""
        if alt_searches:
            footer = f"\n[dim]Alternative searches: {alt_searches[0]}[/dim]"

        return Panel(
            table,
            title=f"[bold red] Exploit Search: {search_info.get('search_term', 'Unknown')}[/bold red]",
            subtitle=footer if footer else None,
            border_style="red",
        )

    def _render_cve_details(self, result: dict[str, Any]) -> Panel:
        """Render detailed CVE information."""
        cve_id = result.get("cve_id", "Unknown")
        details = result.get("cve_details", {})
        exploitability = result.get("exploitability", {})
        remediation = result.get("remediation", {})

        content = Text()
        
        # Header
        severity = details.get("severity_level", "Unknown")
        score = details.get("cvss_score")
        content.append(f"CVE: ", style="bold")
        content.append(f"{cve_id}\n", style="cyan bold")
        content.append(f"Severity: ", style="bold")
        content.append(f"{severity}", style=self._severity_style(severity))
        if score:
            content.append(f" (CVSS: {score})\n")
        else:
            content.append("\n")

        # Attack info
        if details.get("attack_vector"):
            content.append(f"Attack Vector: ", style="bold")
            content.append(f"{details['attack_vector']}\n")
        if details.get("attack_complexity"):
            content.append(f"Complexity: ", style="bold")
            content.append(f"{details['attack_complexity']}\n")

        content.append("\n")

        # Description
        content.append("Description:\n", style="bold underline")
        desc = details.get("description", "No description available")
        content.append(f"{desc[:500]}{'...' if len(desc) > 500 else ''}\n\n")

        # Exploitability
        content.append("Exploitability:\n", style="bold underline")
        if exploitability.get("has_public_exploit"):
            content.append(" PUBLIC EXPLOIT AVAILABLE\n", style="red bold")
        if exploitability.get("has_poc"):
            content.append(" PoC Available\n", style="yellow")
        if exploitability.get("has_patch"):
            content.append(" Patch Available\n", style="green")

        # Exploit references
        exploit_refs = result.get("exploit_references", [])
        if exploit_refs:
            content.append("\nExploit References:\n", style="bold underline")
            for ref in exploit_refs[:3]:
                content.append(f"  • {ref.get('url', 'N/A')}\n", style="cyan")

        return Panel(
            content,
            title=f"[bold cyan] CVE Details: {cve_id}[/bold cyan]",
            border_style="cyan",
        )

    def _render_github_advisories(self, result: dict[str, Any]) -> Panel:
        """Render GitHub Security Advisories results."""
        advisories = result.get("advisories", [])
        search_info = result.get("search_info", {})

        table = Table(
            show_header=True,
            header_style="bold magenta",
            expand=True,
        )
        
        table.add_column("GHSA/CVE", style="magenta", width=20)
        table.add_column("Severity", width=10)
        table.add_column("Package", width=15)
        table.add_column("Summary", overflow="fold")

        for adv in advisories[:15]:
            adv_id = adv.get("ghsa_id") or adv.get("cve_id", "N/A")
            severity = adv.get("severity", "Unknown")
            
            # Get package name from vulnerabilities
            vulns = adv.get("vulnerabilities", [])
            package = vulns[0].get("package", "N/A") if vulns else "N/A"
            
            summary = (adv.get("summary", "")[:50] + "...") if adv.get("summary") else "N/A"
            
            table.add_row(
                adv_id,
                Text(severity, style=self._severity_style(severity)),
                package,
                summary,
            )

        return Panel(
            table,
            title="[bold magenta] GitHub Security Advisories[/bold magenta]",
            border_style="magenta",
        )

    def _render_tech_vulns(self, result: dict[str, Any]) -> Panel:
        """Render comprehensive technology vulnerabilities."""
        tech = result.get("technology", "Unknown")
        version = result.get("version", "")
        summary = result.get("summary", {})
        testing_priority = result.get("testing_priority", [])

        content = Text()
        
        # Header
        content.append(f"Technology: ", style="bold")
        content.append(f"{tech}", style="cyan bold")
        if version:
            content.append(f" v{version}", style="cyan")
        content.append("\n\n")

        # Summary stats
        content.append("Summary:\n", style="bold underline")
        content.append(f"  Total Vulnerabilities: {summary.get('total_vulnerabilities', 0)}\n")
        content.append(f"  With Exploits: ", style="bold")
        content.append(f"{summary.get('with_exploits', 0)}\n", style="red" if summary.get('with_exploits', 0) > 0 else "dim")
        content.append(f"  Critical: {summary.get('critical_count', 0)}, High: {summary.get('high_count', 0)}\n")
        
        attack_vectors = summary.get("attack_vectors", [])
        if attack_vectors:
            content.append(f"  Attack Vectors: {', '.join(attack_vectors)}\n")

        content.append("\n")

        # Testing Priority
        if testing_priority:
            content.append("Testing Priority:\n", style="bold underline")
            for i, item in enumerate(testing_priority[:5], 1):
                vuln_id = item.get("id", "N/A")
                severity = item.get("severity", "Unknown")
                has_exploit = " [EXPLOIT]" if item.get("has_exploit") else ""
                content.append(f"  {i}. ")
                content.append(f"{vuln_id}", style="cyan")
                content.append(f" [{severity}]", style=self._severity_style(severity))
                if has_exploit:
                    content.append(has_exploit, style="red bold")
                content.append("\n")

        # Exploits available
        exploits = result.get("exploits_available", [])
        if exploits:
            content.append(f"\nExploits Found: {len(exploits)}\n", style="red bold")
            for exp in exploits[:3]:
                title = exp.get("title") or exp.get("cve_id", "Unknown")
                content.append(f"  • {title}\n", style="red")

        return Panel(
            content,
            title=f"[bold cyan] Technology Vulnerabilities: {tech}[/bold cyan]",
            border_style="cyan",
        )

    def _render_packetstorm(self, result: dict[str, Any]) -> Panel:
        """Render PacketStorm search results."""
        results = result.get("results", [])
        search_info = result.get("search_info", {})

        if not results:
            return Panel(
                Text(f"No results found. Try: {result.get('direct_search_url', 'N/A')}"),
                title="[bold yellow] PacketStorm Search[/bold yellow]",
                border_style="yellow",
            )

        table = Table(
            show_header=True,
            header_style="bold yellow",
            expand=True,
        )
        
        table.add_column("Title", overflow="fold")
        table.add_column("URL", style="dim", width=40)

        for item in results[:10]:
            title = item.get("title", "N/A")
            url = item.get("url", "N/A")
            table.add_row(title, url)

        return Panel(
            table,
            title=f"[bold yellow] PacketStorm: {search_info.get('search_term', 'Unknown')}[/bold yellow]",
            border_style="yellow",
        )
