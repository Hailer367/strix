"""
StrixDB Repository Knowledge Extraction System

This module enables the AI agent to clone repositories and extract
COMPREHENSIVE, DETAILED information from them into StrixDB.

USE CASE:
When you find a repository full of curated bug bounty resources, tools,
scripts, wordlists, techniques, PDFs, wikis, and other materials - you can
use this system to extract ALL that knowledge into StrixDB for permanent
storage and future use.

FEATURES:
- Clone any git repository
- Scan and categorize all files
- Extract tools, scripts, wordlists, payloads, documentation
- Store with full original content and metadata
- Organize by type for easy retrieval
- Track extraction progress
- Support incremental updates

EXTRACTION CATEGORIES:
- tools: Executables, scripts, CLI tools
- scripts: Shell scripts, Python scripts, automation
- wordlists: Fuzzing wordlists, payloads, dictionaries
- documentation: READMEs, wikis, guides, PDFs (metadata)
- techniques: Attack techniques, methodologies
- references: Links, sources, databases
- templates: Report templates, configuration templates
- payloads: XSS payloads, SQLi payloads, etc.
- exploits: PoC exploits and CVE exploits
- cheatsheets: Quick reference cheatsheets
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from strix.tools.registry import register_tool


logger = logging.getLogger(__name__)


# File type mappings for automatic categorization
FILE_TYPE_MAPPINGS = {
    # Scripts and tools
    ".py": "scripts",
    ".sh": "scripts",
    ".bash": "scripts",
    ".zsh": "scripts",
    ".ps1": "scripts",
    ".rb": "scripts",
    ".pl": "scripts",
    ".go": "tools",
    ".rs": "tools",
    
    # Wordlists and payloads
    ".txt": "wordlists",  # Will be further categorized based on content/path
    ".lst": "wordlists",
    ".dic": "wordlists",
    
    # Documentation
    ".md": "documentation",
    ".rst": "documentation",
    ".html": "documentation",
    ".htm": "documentation",
    ".pdf": "documentation",
    ".doc": "documentation",
    ".docx": "documentation",
    
    # Configuration
    ".yml": "configs",
    ".yaml": "configs",
    ".json": "configs",
    ".toml": "configs",
    ".ini": "configs",
    ".conf": "configs",
    ".cfg": "configs",
    
    # Templates
    ".j2": "templates",
    ".jinja": "templates",
    ".jinja2": "templates",
    ".tmpl": "templates",
    ".template": "templates",
}

# Path patterns for better categorization
PATH_PATTERNS = {
    r"wordlist|fuzzing|fuzz|dict|dictionary": "wordlists",
    r"payload|xss|sqli|injection|shell": "payloads",
    r"exploit|poc|cve": "exploits",
    r"cheatsheet|cheat": "cheatsheets",
    r"technique|method|attack": "techniques",
    r"reference|resource|link|source": "references",
    r"template|report": "templates",
    r"tool|script|bin|util": "tools",
    r"doc|wiki|guide|readme|manual": "documentation",
}


def _get_strixdb_config() -> dict[str, str]:
    """Get StrixDB configuration."""
    from strix.tools.strixdb.strixdb_actions import _get_strixdb_config as get_config
    return get_config()


def _get_headers(token: str) -> dict[str, str]:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sanitize_repo_slug(repo_url: str) -> str:
    """Create a safe slug from a repository URL."""
    # Extract repo name from various URL formats
    # https://github.com/owner/repo.git
    # git@github.com:owner/repo.git
    # owner/repo
    
    repo_url = repo_url.strip()
    
    # Remove .git suffix
    repo_url = repo_url.rstrip('.git')
    
    # Handle SSH format
    if repo_url.startswith('git@'):
        repo_url = repo_url.replace(':', '/').replace('git@', '')
    
    # Handle HTTPS format
    repo_url = re.sub(r'^https?://', '', repo_url)
    
    # Extract owner/repo part
    parts = repo_url.split('/')
    if len(parts) >= 2:
        owner = parts[-2]
        repo = parts[-1]
        slug = f"{owner}_{repo}"
    else:
        slug = parts[-1] if parts else "unknown_repo"
    
    # Sanitize
    slug = re.sub(r'[^\w\-]', '_', slug).lower()
    slug = re.sub(r'_+', '_', slug).strip('_')
    
    return slug


def _categorize_file(file_path: str, content: str = "") -> str:
    """
    Categorize a file based on its path, extension, and content.
    Returns the most appropriate category.
    """
    path_lower = file_path.lower()
    
    # First check path patterns (more specific)
    for pattern, category in PATH_PATTERNS.items():
        if re.search(pattern, path_lower):
            return category
    
    # Then check file extension
    ext = Path(file_path).suffix.lower()
    if ext in FILE_TYPE_MAPPINGS:
        category = FILE_TYPE_MAPPINGS[ext]
        
        # Further categorize .txt files based on path
        if category == "wordlists":
            if any(x in path_lower for x in ["payload", "xss", "sqli", "injection"]):
                return "payloads"
        
        return category
    
    # Default
    return "references"


def _get_or_create_repo_file(
    config: dict[str, str],
    repo_slug: str,
    file_name: str,
    default_content: dict[str, Any] | list[Any],
) -> tuple[dict[str, Any] | list[Any], str | None]:
    """Get existing file content or return default."""
    path = f"extracted_repos/{repo_slug}/{file_name}"
    url = f"{config['api_base']}/repos/{config['repo']}/contents/{path}"
    
    try:
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            content = json.loads(base64.b64decode(data.get("content", "")).decode())
            return content, data.get("sha")
        
        return default_content, None
        
    except (requests.RequestException, json.JSONDecodeError):
        return default_content, None


def _save_repo_file(
    config: dict[str, str],
    repo_slug: str,
    file_name: str,
    content: dict[str, Any] | list[Any] | str,
    sha: str | None = None,
    commit_message: str = "",
    is_binary: bool = False,
) -> bool:
    """Save a file to the repo's directory in StrixDB."""
    path = f"extracted_repos/{repo_slug}/{file_name}"
    url = f"{config['api_base']}/repos/{config['repo']}/contents/{path}"
    
    if isinstance(content, (dict, list)):
        content_str = json.dumps(content, indent=2)
    else:
        content_str = str(content)
    
    content_encoded = base64.b64encode(content_str.encode()).decode()
    
    payload: dict[str, Any] = {
        "message": commit_message or f"[StrixDB] Update {path}",
        "content": content_encoded,
        "branch": config["branch"],
    }
    
    if sha:
        payload["sha"] = sha
    
    try:
        response = requests.put(
            url,
            headers=_get_headers(config["token"]),
            json=payload,
            timeout=30,
        )
        return response.status_code in (200, 201)
    except requests.RequestException:
        return False


def _ensure_repo_directory(config: dict[str, str], repo_slug: str, repo_url: str) -> bool:
    """Ensure the repository extraction directory exists in StrixDB."""
    readme_path = f"extracted_repos/{repo_slug}/README.md"
    url = f"{config['api_base']}/repos/{config['repo']}/contents/{readme_path}"
    
    try:
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 200:
            return True  # Already exists
        
        if response.status_code == 404:
            readme_content = f"""# Extracted Repository: {repo_slug}

## Source Repository
`{repo_url}`

## Contents

This directory contains data extracted from the source repository:

- `manifest.json` - Extraction manifest and metadata
- `index.json` - File index with categories
- `categories/` - Extracted content by category:
  - `tools/` - CLI tools and utilities
  - `scripts/` - Automation scripts
  - `wordlists/` - Fuzzing wordlists
  - `payloads/` - Attack payloads
  - `exploits/` - PoC exploits
  - `documentation/` - Guides and docs
  - `techniques/` - Attack techniques
  - `references/` - Links and sources
  - `templates/` - Templates
  - `cheatsheets/` - Quick references
  - `configs/` - Configuration files

## Auto-generated by StrixDB Repository Extraction System
"""
            content_encoded = base64.b64encode(readme_content.encode()).decode()
            
            create_response = requests.put(
                url,
                headers=_get_headers(config["token"]),
                json={
                    "message": f"[StrixDB] Initialize extracted repo: {repo_slug}",
                    "content": content_encoded,
                    "branch": config["branch"],
                },
                timeout=30,
            )
            
            return create_response.status_code in (200, 201)
        
        return False
        
    except requests.RequestException:
        return False


def _create_extraction_manifest(
    repo_url: str,
    repo_slug: str,
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create the initial extraction manifest."""
    now = datetime.now(timezone.utc).isoformat()
    
    return {
        "id": str(uuid.uuid4())[:12],
        "repo_slug": repo_slug,
        "source_url": repo_url,
        "description": description,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
        "last_extraction_at": now,
        "status": "initialized",  # initialized, extracting, completed, failed, updating
        
        # Extraction stats
        "stats": {
            "total_files_scanned": 0,
            "files_extracted": 0,
            "files_skipped": 0,
            "categories": {},
            "total_size_bytes": 0,
        },
        
        # Category breakdown
        "category_counts": {
            "tools": 0,
            "scripts": 0,
            "wordlists": 0,
            "payloads": 0,
            "exploits": 0,
            "documentation": 0,
            "techniques": 0,
            "references": 0,
            "templates": 0,
            "cheatsheets": 0,
            "configs": 0,
        },
        
        # Extraction history
        "extraction_history": [],
        
        # Important files/resources found
        "highlights": {
            "readme_files": [],
            "tool_files": [],
            "notable_resources": [],
        },
    }


@register_tool(sandbox_execution=True)
def strixdb_repo_extract_init(
    agent_state: Any,
    repo_url: str,
    description: str = "",
    tags: list[str] | None = None,
    clone_depth: int = 1,
) -> dict[str, Any]:
    """
    Initialize a repository extraction session.
    
    This clones the repository locally and prepares it for extraction.
    Use this when you find a repository with valuable resources that
    should be extracted into StrixDB for future use.
    
    Args:
        agent_state: Current agent state
        repo_url: Git repository URL (HTTPS or SSH)
        description: Description of what this repo contains
        tags: Tags for categorization (e.g., ["bugbounty", "wordlists", "tools"])
        clone_depth: Git clone depth (1 for shallow, 0 for full)
    
    Returns:
        Dictionary with extraction session info and file manifest
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured. Ensure STRIXDB_TOKEN is set.",
        }
    
    repo_slug = _sanitize_repo_slug(repo_url)
    
    # Check if already extracted
    existing_manifest, manifest_sha = _get_or_create_repo_file(
        config, repo_slug, "manifest.json", {}
    )
    
    if existing_manifest and manifest_sha:
        return {
            "success": True,
            "message": f"Repository '{repo_slug}' already initialized. Use update functions to add more data.",
            "is_new": False,
            "repo_slug": repo_slug,
            "manifest": existing_manifest,
            "hint": (
                "Repository already exists. Use:\n"
                "- strixdb_repo_extract_scan() to re-scan for new files\n"
                "- strixdb_repo_extract_file() to extract specific files\n"
                "- strixdb_repo_extract_category() to extract by category"
            ),
        }
    
    # Create extraction directory in StrixDB
    if not _ensure_repo_directory(config, repo_slug, repo_url):
        return {
            "success": False,
            "error": f"Failed to create extraction directory for '{repo_slug}'",
        }
    
    # Clone the repository locally (in sandbox)
    clone_dir = f"/tmp/strixdb_extract/{repo_slug}"
    
    try:
        # Clean up any existing directory
        subprocess.run(["rm", "-rf", clone_dir], check=False, timeout=30)
        os.makedirs(os.path.dirname(clone_dir), exist_ok=True)
        
        # Clone with optional depth
        clone_cmd = ["git", "clone"]
        if clone_depth > 0:
            clone_cmd.extend(["--depth", str(clone_depth)])
        clone_cmd.extend([repo_url, clone_dir])
        
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Git clone failed: {result.stderr}",
            }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Git clone timed out after 5 minutes",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Clone failed: {str(e)}",
        }
    
    # Scan the cloned repository
    file_index = []
    category_counts: dict[str, int] = {}
    total_size = 0
    
    try:
        for root, dirs, files in os.walk(clone_dir):
            # Skip .git directory
            if '.git' in dirs:
                dirs.remove('.git')
            
            for file_name in files:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, clone_dir)
                
                try:
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size
                    total_size += file_size
                    
                    # Skip very large files (> 5MB)
                    if file_size > 5 * 1024 * 1024:
                        continue
                    
                    # Categorize the file
                    category = _categorize_file(relative_path)
                    category_counts[category] = category_counts.get(category, 0) + 1
                    
                    file_index.append({
                        "path": relative_path,
                        "category": category,
                        "size": file_size,
                        "extension": Path(file_name).suffix.lower(),
                        "extracted": False,
                    })
                    
                except OSError:
                    continue
                    
    except Exception as e:
        logger.warning(f"Error scanning repository: {e}")
    
    # Create manifest
    manifest = _create_extraction_manifest(
        repo_url=repo_url,
        repo_slug=repo_slug,
        description=description,
        tags=tags,
    )
    
    manifest["stats"]["total_files_scanned"] = len(file_index)
    manifest["stats"]["total_size_bytes"] = total_size
    manifest["category_counts"] = category_counts
    manifest["status"] = "scanned"
    
    # Save manifest
    if not _save_repo_file(
        config,
        repo_slug,
        "manifest.json",
        manifest,
        commit_message=f"[StrixDB] Initialize extraction: {repo_slug}",
    ):
        return {
            "success": False,
            "error": "Failed to save manifest",
        }
    
    # Save file index
    if not _save_repo_file(
        config,
        repo_slug,
        "index.json",
        {"files": file_index, "updated_at": datetime.now(timezone.utc).isoformat()},
        commit_message=f"[StrixDB] Save file index: {repo_slug}",
    ):
        return {
            "success": False,
            "error": "Failed to save file index",
        }
    
    logger.info(f"[StrixDB] Initialized extraction for {repo_slug}: {len(file_index)} files")
    
    return {
        "success": True,
        "message": f"Repository '{repo_slug}' initialized for extraction",
        "is_new": True,
        "repo_slug": repo_slug,
        "clone_path": clone_dir,
        "stats": {
            "total_files": len(file_index),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "categories": category_counts,
        },
        "next_steps": (
            "Repository cloned and scanned! Now extract content:\n"
            "1. Use strixdb_repo_extract_category() to extract all files in a category\n"
            "2. Use strixdb_repo_extract_file() to extract specific files\n"
            "3. Use strixdb_repo_extract_readme() to extract documentation\n"
            "4. Use strixdb_repo_extract_all() to extract everything\n\n"
            f"Clone available at: {clone_dir}"
        ),
    }


@register_tool(sandbox_execution=True)
def strixdb_repo_extract_file(
    agent_state: Any,
    repo_slug: str,
    file_path: str,
    custom_category: str | None = None,
    custom_name: str | None = None,
    custom_description: str = "",
    custom_tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Extract a specific file from a cloned repository into StrixDB.
    
    Reads the file content and saves it to the appropriate category
    in StrixDB with full metadata.
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug from strixdb_repo_extract_init
        file_path: Relative path to the file within the repo
        custom_category: Override auto-detected category
        custom_name: Custom name for the item in StrixDB
        custom_description: Description of the file/content
        custom_tags: Additional tags
    
    Returns:
        Dictionary with extraction result
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    clone_dir = f"/tmp/strixdb_extract/{repo_slug}"
    full_path = os.path.join(clone_dir, file_path)
    
    if not os.path.exists(full_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}. Make sure the repo is cloned.",
        }
    
    # Read file content
    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to read file: {str(e)}",
        }
    
    # Determine category
    category = custom_category or _categorize_file(file_path, content)
    
    # Generate name
    name = custom_name or Path(file_path).stem
    safe_name = re.sub(r'[^\w\-]', '_', name).lower()
    
    # Create item data
    now = datetime.now(timezone.utc).isoformat()
    item_id = f"ext_{str(uuid.uuid4())[:8]}"
    
    item_data = {
        "id": item_id,
        "name": name,
        "original_path": file_path,
        "source_repo": repo_slug,
        "category": category,
        "description": custom_description or f"Extracted from {repo_slug}: {file_path}",
        "tags": custom_tags or [],
        "content": content,
        "content_length": len(content),
        "extension": Path(file_path).suffix.lower(),
        "extracted_at": now,
        "hash": hashlib.md5(content.encode()).hexdigest()[:12],
    }
    
    # Save to category directory
    save_path = f"categories/{category}/{safe_name}.json"
    
    if not _save_repo_file(
        config,
        repo_slug,
        save_path,
        item_data,
        commit_message=f"[StrixDB] Extract: {file_path}",
    ):
        return {
            "success": False,
            "error": "Failed to save extracted file",
        }
    
    # Update index to mark as extracted
    index, index_sha = _get_or_create_repo_file(
        config, repo_slug, "index.json", {"files": []}
    )
    
    if index and index_sha:
        for f in index.get("files", []):
            if f.get("path") == file_path:
                f["extracted"] = True
                f["extracted_to"] = save_path
                break
        
        _save_repo_file(
            config,
            repo_slug,
            "index.json",
            index,
            sha=index_sha,
            commit_message=f"[StrixDB] Update index: {file_path} extracted",
        )
    
    # Update manifest stats
    manifest, manifest_sha = _get_or_create_repo_file(
        config, repo_slug, "manifest.json", {}
    )
    
    if manifest and manifest_sha:
        if "stats" not in manifest:
            manifest["stats"] = {}
        manifest["stats"]["files_extracted"] = manifest["stats"].get("files_extracted", 0) + 1
        manifest["updated_at"] = now
        
        _save_repo_file(
            config,
            repo_slug,
            "manifest.json",
            manifest,
            sha=manifest_sha,
            commit_message=f"[StrixDB] Update manifest stats",
        )
    
    logger.info(f"[StrixDB] Extracted {file_path} to {category}")
    
    return {
        "success": True,
        "message": f"Successfully extracted '{file_path}' to category '{category}'",
        "item": {
            "id": item_id,
            "name": name,
            "category": category,
            "path": save_path,
            "content_preview": content[:500] + "..." if len(content) > 500 else content,
        },
    }


@register_tool(sandbox_execution=True)
def strixdb_repo_extract_category(
    agent_state: Any,
    repo_slug: str,
    category: str,
    max_files: int = 100,
    max_file_size_kb: int = 500,
    include_extensions: list[str] | None = None,
    exclude_extensions: list[str] | None = None,
) -> dict[str, Any]:
    """
    Extract all files of a specific category from a cloned repository.
    
    Batch extracts files that belong to the specified category
    (as determined by the scanning process).
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug from strixdb_repo_extract_init
        category: Category to extract (tools, scripts, wordlists, payloads, etc.)
        max_files: Maximum number of files to extract
        max_file_size_kb: Skip files larger than this
        include_extensions: Only include these extensions
        exclude_extensions: Exclude these extensions
    
    Returns:
        Dictionary with extraction results
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    # Load index
    index, _ = _get_or_create_repo_file(
        config, repo_slug, "index.json", {"files": []}
    )
    
    if not index or not index.get("files"):
        return {
            "success": False,
            "error": f"No file index found for '{repo_slug}'. Run strixdb_repo_extract_init first.",
        }
    
    # Filter files by category
    files_to_extract = []
    for f in index.get("files", []):
        if f.get("extracted"):
            continue
        if f.get("category") != category:
            continue
        if f.get("size", 0) > max_file_size_kb * 1024:
            continue
        
        ext = f.get("extension", "").lower()
        if include_extensions and ext not in include_extensions:
            continue
        if exclude_extensions and ext in exclude_extensions:
            continue
        
        files_to_extract.append(f)
    
    files_to_extract = files_to_extract[:max_files]
    
    if not files_to_extract:
        return {
            "success": True,
            "message": f"No files to extract for category '{category}'",
            "extracted_count": 0,
        }
    
    # Extract each file
    extracted = []
    failed = []
    
    for f in files_to_extract:
        result = strixdb_repo_extract_file(
            agent_state,
            repo_slug=repo_slug,
            file_path=f["path"],
        )
        
        if result.get("success"):
            extracted.append(f["path"])
        else:
            failed.append({"path": f["path"], "error": result.get("error", "Unknown")})
    
    logger.info(f"[StrixDB] Category extraction complete: {len(extracted)} extracted, {len(failed)} failed")
    
    return {
        "success": True,
        "message": f"Extracted {len(extracted)} files from category '{category}'",
        "category": category,
        "extracted_count": len(extracted),
        "failed_count": len(failed),
        "extracted_files": extracted[:20],  # Show first 20
        "failed_files": failed[:10] if failed else [],
    }


@register_tool(sandbox_execution=True)
def strixdb_repo_extract_all(
    agent_state: Any,
    repo_slug: str,
    max_files_per_category: int = 50,
    max_file_size_kb: int = 500,
    categories: list[str] | None = None,
    skip_categories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Extract all files from a cloned repository into StrixDB.
    
    Comprehensively extracts all valuable content organized by category.
    Use this when you want to capture EVERYTHING from a repository.
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug from strixdb_repo_extract_init
        max_files_per_category: Max files to extract per category
        max_file_size_kb: Skip files larger than this
        categories: Only extract these categories (default: all)
        skip_categories: Skip these categories
    
    Returns:
        Dictionary with comprehensive extraction results
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    # Load manifest to get category list
    manifest, _ = _get_or_create_repo_file(
        config, repo_slug, "manifest.json", {}
    )
    
    if not manifest:
        return {
            "success": False,
            "error": f"Repository '{repo_slug}' not initialized. Run strixdb_repo_extract_init first.",
        }
    
    all_categories = list(manifest.get("category_counts", {}).keys())
    
    if categories:
        all_categories = [c for c in all_categories if c in categories]
    if skip_categories:
        all_categories = [c for c in all_categories if c not in skip_categories]
    
    results: dict[str, dict[str, Any]] = {}
    total_extracted = 0
    total_failed = 0
    
    for category in all_categories:
        result = strixdb_repo_extract_category(
            agent_state,
            repo_slug=repo_slug,
            category=category,
            max_files=max_files_per_category,
            max_file_size_kb=max_file_size_kb,
        )
        
        results[category] = {
            "extracted": result.get("extracted_count", 0),
            "failed": result.get("failed_count", 0),
        }
        
        total_extracted += result.get("extracted_count", 0)
        total_failed += result.get("failed_count", 0)
    
    # Update manifest
    manifest, manifest_sha = _get_or_create_repo_file(
        config, repo_slug, "manifest.json", {}
    )
    
    if manifest and manifest_sha:
        manifest["status"] = "completed"
        manifest["stats"]["files_extracted"] = total_extracted
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        manifest["last_extraction_at"] = datetime.now(timezone.utc).isoformat()
        
        manifest["extraction_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "full_extraction",
            "files_extracted": total_extracted,
            "files_failed": total_failed,
        })
        
        _save_repo_file(
            config,
            repo_slug,
            "manifest.json",
            manifest,
            sha=manifest_sha,
            commit_message=f"[StrixDB] Complete extraction: {repo_slug}",
        )
    
    logger.info(f"[StrixDB] Full extraction complete: {total_extracted} files")
    
    return {
        "success": True,
        "message": f"Full extraction completed for '{repo_slug}'",
        "total_extracted": total_extracted,
        "total_failed": total_failed,
        "by_category": results,
        "hint": (
            "All available files have been extracted. Use:\n"
            "- strixdb_search() to find extracted content\n"
            "- strixdb_repo_extract_status() to see extraction details\n"
            "- strixdb_repo_list_extracted() to browse extracted files"
        ),
    }


@register_tool(sandbox_execution=False)
def strixdb_repo_extract_status(
    agent_state: Any,
    repo_slug: str,
) -> dict[str, Any]:
    """
    Get the extraction status for a repository.
    
    Shows what has been extracted, what's pending, and statistics.
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug
    
    Returns:
        Dictionary with extraction status and statistics
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    # Load manifest
    manifest, _ = _get_or_create_repo_file(
        config, repo_slug, "manifest.json", {}
    )
    
    if not manifest:
        return {
            "success": False,
            "error": f"Repository '{repo_slug}' not found",
        }
    
    # Load index for detailed stats
    index, _ = _get_or_create_repo_file(
        config, repo_slug, "index.json", {"files": []}
    )
    
    files = index.get("files", [])
    extracted_count = sum(1 for f in files if f.get("extracted"))
    pending_count = sum(1 for f in files if not f.get("extracted"))
    
    # Group pending by category
    pending_by_category: dict[str, int] = {}
    for f in files:
        if not f.get("extracted"):
            cat = f.get("category", "unknown")
            pending_by_category[cat] = pending_by_category.get(cat, 0) + 1
    
    return {
        "success": True,
        "repo_slug": repo_slug,
        "source_url": manifest.get("source_url"),
        "status": manifest.get("status", "unknown"),
        "stats": {
            "total_files": len(files),
            "extracted": extracted_count,
            "pending": pending_count,
            "extraction_percentage": round(extracted_count / len(files) * 100, 1) if files else 0,
        },
        "category_counts": manifest.get("category_counts", {}),
        "pending_by_category": pending_by_category,
        "extraction_history": manifest.get("extraction_history", [])[-5:],
        "created_at": manifest.get("created_at"),
        "last_extraction_at": manifest.get("last_extraction_at"),
    }


@register_tool(sandbox_execution=False)
def strixdb_repo_list_extracted(
    agent_state: Any,
    repo_slug: str,
    category: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List extracted files from a repository.
    
    Browse what has been extracted and stored in StrixDB.
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug
        category: Filter by category (optional)
        limit: Maximum items to return
    
    Returns:
        Dictionary with list of extracted items
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    # Load index
    index, _ = _get_or_create_repo_file(
        config, repo_slug, "index.json", {"files": []}
    )
    
    files = index.get("files", [])
    extracted = [f for f in files if f.get("extracted")]
    
    if category:
        extracted = [f for f in extracted if f.get("category") == category]
    
    extracted = extracted[:limit]
    
    return {
        "success": True,
        "repo_slug": repo_slug,
        "total_extracted": len(extracted),
        "items": [
            {
                "path": f.get("path"),
                "category": f.get("category"),
                "size": f.get("size"),
                "extracted_to": f.get("extracted_to"),
            }
            for f in extracted
        ],
    }


@register_tool(sandbox_execution=False)
def strixdb_repo_get_item(
    agent_state: Any,
    repo_slug: str,
    category: str,
    item_name: str,
) -> dict[str, Any]:
    """
    Get a specific extracted item from a repository.
    
    Retrieve the full content of an extracted file.
    
    Args:
        agent_state: Current agent state
        repo_slug: Repository slug
        category: Item category
        item_name: Item name (without extension)
    
    Returns:
        Dictionary with item content and metadata
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    # Try to load the item
    safe_name = re.sub(r'[^\w\-]', '_', item_name).lower()
    item_path = f"categories/{category}/{safe_name}.json"
    
    item, _ = _get_or_create_repo_file(
        config, repo_slug, item_path, {}
    )
    
    if not item:
        return {
            "success": False,
            "error": f"Item '{item_name}' not found in category '{category}'",
        }
    
    return {
        "success": True,
        "item": item,
    }


@register_tool(sandbox_execution=False)
def strixdb_repo_search(
    agent_state: Any,
    query: str,
    repo_slug: str | None = None,
    category: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search across extracted repository content.
    
    Find files and content matching your query across all or specific
    extracted repositories.
    
    Args:
        agent_state: Current agent state
        query: Search query
        repo_slug: Limit to specific repo (optional)
        category: Limit to specific category (optional)
        limit: Maximum results
    
    Returns:
        Dictionary with search results
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    try:
        # Use GitHub code search API
        search_query = f"repo:{config['repo']} {query}"
        
        if repo_slug:
            search_query += f" path:extracted_repos/{repo_slug}"
        else:
            search_query += " path:extracted_repos"
        
        if category:
            search_query += f" path:categories/{category}"
        
        url = f"{config['api_base']}/search/code"
        params = {
            "q": search_query,
            "per_page": min(limit, 100),
        }
        
        response = requests.get(
            url,
            headers=_get_headers(config["token"]),
            params=params,
            timeout=30,
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"Search failed: {response.status_code}",
                "results": [],
            }
        
        data = response.json()
        results = []
        
        for item in data.get("items", []):
            path = item.get("path", "")
            
            # Parse path to extract repo_slug and category
            parts = path.split("/")
            if len(parts) >= 4 and parts[0] == "extracted_repos":
                results.append({
                    "repo_slug": parts[1],
                    "category": parts[3] if len(parts) > 3 and parts[2] == "categories" else None,
                    "file": parts[-1],
                    "path": path,
                    "score": item.get("score", 0),
                })
        
        return {
            "success": True,
            "query": query,
            "total_count": data.get("total_count", len(results)),
            "results": results[:limit],
        }
        
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Search failed: {e}",
            "results": [],
        }


@register_tool(sandbox_execution=False)
def strixdb_repo_list(
    agent_state: Any,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List all extracted repositories in StrixDB.
    
    Get an overview of all repositories that have been extracted.
    
    Args:
        agent_state: Current agent state
        limit: Maximum repositories to return
    
    Returns:
        Dictionary with list of extracted repositories
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    try:
        # List contents of extracted_repos directory
        url = f"{config['api_base']}/repos/{config['repo']}/contents/extracted_repos"
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 404:
            return {"success": True, "repositories": [], "message": "No extracted repositories found"}
        
        if response.status_code != 200:
            return {"success": False, "error": f"Failed to list repos: {response.status_code}"}
        
        items = response.json()
        repos = []
        
        for item in items[:limit]:
            if item.get("type") == "dir":
                repo_slug = item.get("name")
                
                # Load manifest for details
                manifest, _ = _get_or_create_repo_file(
                    config, repo_slug, "manifest.json", {}
                )
                
                repos.append({
                    "slug": repo_slug,
                    "source_url": manifest.get("source_url", ""),
                    "status": manifest.get("status", "unknown"),
                    "files_extracted": manifest.get("stats", {}).get("files_extracted", 0),
                    "categories": list(manifest.get("category_counts", {}).keys()),
                    "tags": manifest.get("tags", []),
                    "created_at": manifest.get("created_at"),
                })
        
        return {
            "success": True,
            "repositories": repos,
            "total": len(repos),
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Request failed: {e}"}
