"""CVE/Exploit Database Integration for Strix.

This module provides integration with multiple vulnerability databases:
- NVD (National Vulnerability Database)
- Exploit-DB
- GitHub Security Advisories
- PacketStorm

Helps the AI agent find and use known vulnerabilities for identified technologies.
"""

from .cve_database_actions import (
    query_cve_database,
    search_exploits,
    get_cve_details,
    search_github_advisories,
    get_technology_vulnerabilities,
    search_packetstorm,
)


__all__ = [
    "query_cve_database",
    "search_exploits",
    "get_cve_details",
    "search_github_advisories",
    "get_technology_vulnerabilities",
    "search_packetstorm",
]
