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

=== MAJOR NEW FEATURES ===

## 1. TARGET TRACKING SYSTEM (NEW!)

Comprehensive target management for scan continuity across sessions:

- strixdb_target_init() - Initialize a new target for tracking
- strixdb_target_session_start() - Start a scan session (loads previous context!)
- strixdb_target_session_end() - End session with continuation notes
- strixdb_target_add_finding() - Record vulnerability findings
- strixdb_target_add_endpoint() - Track discovered endpoints
- strixdb_target_add_note() - Add observations and notes
- strixdb_target_add_technology() - Record identified technologies
- strixdb_target_update_progress() - Track what has been tested
- strixdb_target_get() - Get full target data
- strixdb_target_list() - List all tracked targets

### Key Benefits:
- Never repeat unnecessary work between sessions
- Comprehensive finding tracking with full details
- Smart session continuation with context awareness
- Progress tracking to know what's been tested

## 2. REPOSITORY KNOWLEDGE EXTRACTION (NEW!)

Extract EVERYTHING valuable from repositories into StrixDB:

- strixdb_repo_extract_init() - Clone and scan a repository
- strixdb_repo_extract_file() - Extract specific file
- strixdb_repo_extract_category() - Extract all files of a category
- strixdb_repo_extract_all() - Extract everything
- strixdb_repo_extract_status() - Check extraction progress
- strixdb_repo_list_extracted() - Browse extracted content
- strixdb_repo_get_item() - Get specific extracted item
- strixdb_repo_search() - Search across extractions
- strixdb_repo_list() - List all extracted repos

### Use Cases:
- Clone bug bounty resource repos and extract all tools/wordlists
- Build a personal knowledge base from curated sources
- Extract techniques, methodologies, and reference materials

=== ORIGINAL CATEGORIES ===

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

# Original StrixDB actions
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

# NEW: Target Tracking System
from .strixdb_targets import (
    strixdb_target_init,
    strixdb_target_session_start,
    strixdb_target_session_end,
    strixdb_target_add_finding,
    strixdb_target_add_endpoint,
    strixdb_target_add_note,
    strixdb_target_add_technology,
    strixdb_target_update_progress,
    strixdb_target_get,
    strixdb_target_list,
)

# NEW: Repository Knowledge Extraction
from .strixdb_repo_extract import (
    strixdb_repo_extract_init,
    strixdb_repo_extract_file,
    strixdb_repo_extract_category,
    strixdb_repo_extract_all,
    strixdb_repo_extract_status,
    strixdb_repo_list_extracted,
    strixdb_repo_get_item,
    strixdb_repo_search,
    strixdb_repo_list,
)


__all__ = [
    # Original StrixDB
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
    
    # Target Tracking System
    "strixdb_target_init",
    "strixdb_target_session_start",
    "strixdb_target_session_end",
    "strixdb_target_add_finding",
    "strixdb_target_add_endpoint",
    "strixdb_target_add_note",
    "strixdb_target_add_technology",
    "strixdb_target_update_progress",
    "strixdb_target_get",
    "strixdb_target_list",
    
    # Repository Extraction
    "strixdb_repo_extract_init",
    "strixdb_repo_extract_file",
    "strixdb_repo_extract_category",
    "strixdb_repo_extract_all",
    "strixdb_repo_extract_status",
    "strixdb_repo_list_extracted",
    "strixdb_repo_get_item",
    "strixdb_repo_search",
    "strixdb_repo_list",
]
