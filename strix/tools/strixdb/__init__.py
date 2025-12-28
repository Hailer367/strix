"""
StrixDB Module - Permanent GitHub-based Knowledge Repository

This module provides tools for the AI agent to store and retrieve useful artifacts
in a permanent GitHub repository (StrixDB). The agent acts as an enthusiastic collector,
automatically storing scripts, tools, exploits, methods, knowledge, and other useful
items for future reference across all engagements.

SIMPLIFIED CONFIGURATION (v2.0):
- Repository is always named "StrixDB" 
- Token comes from STRIXDB_TOKEN environment variable (set via GitHub Secrets)
- The owner is automatically detected from the token

Categories supported (can be extended dynamically):
- scripts: Automation scripts and tools
- exploits: Working exploits and PoCs
- knowledge: Security knowledge and notes
- libraries: Reusable code libraries
- sources: Wordlists, data sources, references
- methods: Attack methodologies
- tools: Custom security tools
- configs: Configuration files and templates
- wordlists: Custom wordlists for fuzzing
- payloads: Useful payloads for attacks
- templates: Report and code templates
- notes: Quick notes and findings

The AI can create NEW categories dynamically using strixdb_create_category()!

Environment Variables:
- STRIXDB_TOKEN: GitHub personal access token with repo permissions (REQUIRED)
- STRIXDB_REPO: Override repository name (optional, defaults to "StrixDB")
- STRIXDB_BRANCH: Branch to use (default: "main")
"""

from .strixdb_actions import (
    strixdb_create_category,
    strixdb_delete,
    strixdb_export,
    strixdb_get,
    strixdb_get_categories,
    strixdb_get_config_status,
    strixdb_get_stats,
    strixdb_import_item,
    strixdb_list,
    strixdb_save,
    strixdb_search,
    strixdb_update,
)


__all__ = [
    "strixdb_create_category",
    "strixdb_delete",
    "strixdb_export",
    "strixdb_get",
    "strixdb_get_categories",
    "strixdb_get_config_status",
    "strixdb_get_stats",
    "strixdb_import_item",
    "strixdb_list",
    "strixdb_save",
    "strixdb_search",
    "strixdb_update",
]
