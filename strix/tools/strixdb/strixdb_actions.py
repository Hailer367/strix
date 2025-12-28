"""
StrixDB Actions - GitHub-based persistent storage for AI agent artifacts.

This module provides tools for the AI agent to interact with StrixDB,
a permanent GitHub repository for storing and retrieving useful artifacts
like scripts, exploits, tools, knowledge, methods, and more.

CONFIGURATION:
- The StrixDB repository is always named "StrixDB" and is owned by the user
- Authentication is via STRIXDB_TOKEN (GitHub token from repository secrets)
- The token is automatically retrieved from GitHub Actions secrets

IMPORTANT: StrixDB uses a fixed repository name "StrixDB" for simplicity.
The repository owner is determined from the token's associated user.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from strix.tools.registry import register_tool


logger = logging.getLogger(__name__)

# Default categories (can be extended dynamically by the AI)
DEFAULT_CATEGORIES = [
    "scripts",
    "exploits",
    "knowledge",
    "libraries",
    "sources",
    "methods",
    "tools",
    "configs",
    "wordlists",
    "payloads",
    "templates",
    "notes",
]

# Category descriptions for documentation
CATEGORY_DESCRIPTIONS = {
    "scripts": "Automation scripts, shell scripts, and utility scripts",
    "exploits": "Working exploits, PoCs, and vulnerability demonstrations",
    "knowledge": "Security knowledge, research notes, and documentation",
    "libraries": "Reusable code libraries and modules",
    "sources": "Data sources, references, and external resource links",
    "methods": "Attack methodologies, techniques, and procedures",
    "tools": "Custom security tools and utilities",
    "configs": "Configuration files, templates, and settings",
    "wordlists": "Custom wordlists for fuzzing and enumeration",
    "payloads": "Useful payloads for various attack types",
    "templates": "Report templates, code templates, and boilerplates",
    "notes": "Quick notes and temporary findings",
}

# Runtime storage for dynamically created categories
_dynamic_categories: set[str] = set()


def _get_strixdb_config() -> dict[str, str]:
    """
    Get StrixDB configuration.
    
    The repository name is always 'StrixDB'.
    The owner is determined by fetching the authenticated user from the token.
    Token comes from STRIXDB_TOKEN environment variable (set via GitHub Secrets).
    """
    token = os.getenv("STRIXDB_TOKEN", "")
    branch = os.getenv("STRIXDB_BRANCH", "main")
    
    # Repository name is always StrixDB
    repo_name = "StrixDB"
    
    # Get the owner from the token
    owner = ""
    if token:
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers=_get_headers(token),
                timeout=10,
            )
            if response.status_code == 200:
                owner = response.json().get("login", "")
        except requests.RequestException:
            pass
    
    # Allow override via environment for flexibility
    repo_override = os.getenv("STRIXDB_REPO", "")
    if repo_override:
        # If full repo path is provided (owner/repo), use it
        if "/" in repo_override:
            return {
                "repo": repo_override,
                "token": token,
                "branch": branch,
                "api_base": "https://api.github.com",
            }
        # Otherwise treat as just repo name with detected owner
        repo_name = repo_override
    
    repo = f"{owner}/{repo_name}" if owner else ""
    
    return {
        "repo": repo,
        "token": token,
        "branch": branch,
        "api_base": "https://api.github.com",
    }


def _get_headers(token: str) -> dict[str, str]:
    """Get headers for GitHub API requests."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sanitize_name(name: str) -> str:
    """Sanitize a name for use as a filename."""
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    # Remove or replace invalid characters
    name = re.sub(r'[^\w\-.]', '_', name)
    # Remove multiple underscores
    name = re.sub(r'_+', '_', name)
    # Trim underscores from ends
    name = name.strip('_')
    return name


def _generate_item_id() -> str:
    """Generate a unique item ID."""
    return str(uuid.uuid4())[:8]


def _get_file_path(category: str, name: str, extension: str = ".json") -> str:
    """Generate the file path for an item."""
    sanitized_name = _sanitize_name(name)
    return f"{category}/{sanitized_name}{extension}"


def _get_valid_categories() -> list[str]:
    """Get all valid categories (default + dynamically created)."""
    return list(set(DEFAULT_CATEGORIES) | _dynamic_categories)


def _create_metadata(
    name: str,
    description: str,
    tags: list[str],
    category: str,
    content_type: str = "text",
) -> dict[str, Any]:
    """Create metadata for an item."""
    return {
        "id": _generate_item_id(),
        "name": name,
        "description": description,
        "tags": tags,
        "category": category,
        "content_type": content_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }


def _ensure_category_exists(category: str, config: dict[str, str]) -> bool:
    """
    Ensure a category directory exists in StrixDB.
    Creates it if it doesn't exist.
    Returns True if successful, False otherwise.
    """
    if not config["repo"] or not config["token"]:
        return False
    
    try:
        # Check if directory exists
        url = f"{config['api_base']}/repos/{config['repo']}/contents/{category}"
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 200:
            return True  # Already exists
        
        if response.status_code == 404:
            # Create the directory with a README
            readme_content = f"""# {category.title()}

This category was automatically created by StrixDB.

{CATEGORY_DESCRIPTIONS.get(category, 'Custom category for storing related items.')}

## Contents

Items in this category will be listed here as they are added.
"""
            readme_encoded = base64.b64encode(readme_content.encode()).decode()
            
            create_url = f"{config['api_base']}/repos/{config['repo']}/contents/{category}/README.md"
            create_response = requests.put(
                create_url,
                headers=_get_headers(config["token"]),
                json={
                    "message": f"[StrixDB] Create category: {category}",
                    "content": readme_encoded,
                    "branch": config["branch"],
                },
                timeout=30,
            )
            
            if create_response.status_code in (200, 201):
                _dynamic_categories.add(category)
                logger.info(f"[StrixDB] Created new category: {category}")
                return True
        
        return False
        
    except requests.RequestException as e:
        logger.exception(f"[StrixDB] Failed to ensure category exists: {e}")
        return False


@register_tool(sandbox_execution=False)
def strixdb_create_category(
    agent_state: Any,
    category_name: str,
    description: str = "",
) -> dict[str, Any]:
    """
    Create a new category in StrixDB.
    
    The AI agent can dynamically create new categories as needed.
    This is useful when existing categories don't fit the content.
    
    Args:
        agent_state: Current agent state
        category_name: Name of the new category (lowercase, no spaces)
        description: Description of what this category is for
    
    Returns:
        Dictionary with operation result
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured. Ensure STRIXDB_TOKEN is set.",
        }
    
    # Sanitize category name
    category_name = category_name.lower().replace(" ", "_")
    category_name = re.sub(r'[^\w]', '', category_name)
    
    if not category_name:
        return {
            "success": False,
            "error": "Invalid category name. Use lowercase letters and underscores only.",
        }
    
    # Update description if provided
    if description:
        CATEGORY_DESCRIPTIONS[category_name] = description
    
    # Create the category
    if _ensure_category_exists(category_name, config):
        return {
            "success": True,
            "message": f"Category '{category_name}' is ready to use",
            "category": category_name,
            "description": description or CATEGORY_DESCRIPTIONS.get(category_name, ""),
        }
    
    return {
        "success": False,
        "error": f"Failed to create category '{category_name}'",
    }


@register_tool(sandbox_execution=False)
def strixdb_save(
    agent_state: Any,
    category: str,
    name: str,
    content: str,
    description: str = "",
    tags: list[str] | None = None,
    content_type: str = "text",
) -> dict[str, Any]:
    """
    Save an item to StrixDB.
    
    The AI agent uses this to permanently store useful artifacts like scripts,
    exploits, knowledge, tools, and other items for future reference.
    
    If the category doesn't exist, it will be created automatically.
    
    Args:
        agent_state: Current agent state
        category: Category for the item (can be new or existing)
        name: Name of the item
        content: Content to save
        description: Description of the item
        tags: List of tags for categorization
        content_type: Type of content (text, script, json, binary)
    
    Returns:
        Dictionary with operation result
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured. Ensure STRIXDB_TOKEN is set in your GitHub secrets.",
            "hint": "Add STRIXDB_TOKEN to your repository secrets with a GitHub PAT that has repo access.",
            "item": None,
        }
    
    # Sanitize category name
    category = category.lower().replace(" ", "_")
    
    # Ensure category exists (create if needed)
    if not _ensure_category_exists(category, config):
        return {
            "success": False,
            "error": f"Failed to access or create category '{category}'",
            "item": None,
        }
    
    if tags is None:
        tags = []
    
    # Create metadata
    metadata = _create_metadata(name, description, tags, category, content_type)
    
    # Determine file extension based on content type
    extensions = {
        "text": ".md",
        "script": ".sh" if "bash" in name.lower() or "shell" in name.lower() else ".py",
        "json": ".json",
        "python": ".py",
        "javascript": ".js",
        "yaml": ".yml",
        "binary": ".bin",
    }
    extension = extensions.get(content_type, ".txt")
    
    # Create content file path
    content_path = _get_file_path(category, name, extension)
    metadata_path = _get_file_path(category, f"{_sanitize_name(name)}_meta", ".json")
    
    try:
        # Save content file
        content_encoded = base64.b64encode(content.encode()).decode()
        
        url = f"{config['api_base']}/repos/{config['repo']}/contents/{content_path}"
        
        # Check if file exists
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        payload: dict[str, Any] = {
            "message": f"[StrixDB] Add {category}/{name}",
            "content": content_encoded,
            "branch": config["branch"],
        }
        
        if response.status_code == 200:
            # File exists, update it
            sha = response.json().get("sha")
            payload["sha"] = sha
            payload["message"] = f"[StrixDB] Update {category}/{name}"
            metadata["version"] = response.json().get("version", 1) + 1
        
        response = requests.put(
            url,
            headers=_get_headers(config["token"]),
            json=payload,
            timeout=30,
        )
        
        if response.status_code not in (200, 201):
            return {
                "success": False,
                "error": f"Failed to save content: {response.status_code} - {response.text}",
                "item": None,
            }
        
        # Save metadata file
        metadata["file_path"] = content_path
        metadata_encoded = base64.b64encode(json.dumps(metadata, indent=2).encode()).decode()
        
        meta_url = f"{config['api_base']}/repos/{config['repo']}/contents/{metadata_path}"
        
        # Check if metadata exists
        meta_response = requests.get(meta_url, headers=_get_headers(config["token"]), timeout=30)
        
        meta_payload: dict[str, Any] = {
            "message": f"[StrixDB] Add metadata for {category}/{name}",
            "content": metadata_encoded,
            "branch": config["branch"],
        }
        
        if meta_response.status_code == 200:
            meta_sha = meta_response.json().get("sha")
            meta_payload["sha"] = meta_sha
            meta_payload["message"] = f"[StrixDB] Update metadata for {category}/{name}"
        
        requests.put(
            meta_url,
            headers=_get_headers(config["token"]),
            json=meta_payload,
            timeout=30,
        )
        
        logger.info(f"[StrixDB] Saved item: {category}/{name}")
        
        return {
            "success": True,
            "message": f"Successfully saved '{name}' to StrixDB in category '{category}'",
            "item": {
                "id": metadata["id"],
                "name": name,
                "category": category,
                "path": content_path,
                "tags": tags,
            },
        }
        
    except requests.RequestException as e:
        logger.exception(f"[StrixDB] Failed to save item: {e}")
        return {
            "success": False,
            "error": f"Request failed: {e!s}",
            "item": None,
        }


@register_tool(sandbox_execution=False)
def strixdb_search(
    agent_state: Any,
    query: str,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search for items in StrixDB.
    
    Args:
        agent_state: Current agent state
        query: Search query (searches name, description, and content)
        category: Optional category filter
        tags: Optional tags filter
        limit: Maximum number of results
    
    Returns:
        Dictionary with search results
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
            "results": [],
        }
    
    try:
        # Search using GitHub Code Search API
        search_query = f"repo:{config['repo']} {query}"
        if category:
            search_query += f" path:{category}/"
        
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
            
            # Skip metadata files in results
            if "_meta.json" in path:
                continue
            
            # Extract category from path
            parts = path.split("/")
            item_category = parts[0] if parts else "unknown"
            item_name = parts[-1] if parts else path
            
            # Apply tag filter if provided
            if tags:
                # Fetch metadata to check tags
                meta_path = path.replace(item_name, f"{item_name.rsplit('.', 1)[0]}_meta.json")
                meta_url = f"{config['api_base']}/repos/{config['repo']}/contents/{meta_path}"
                meta_response = requests.get(
                    meta_url,
                    headers=_get_headers(config["token"]),
                    timeout=10,
                )
                if meta_response.status_code == 200:
                    meta_content = base64.b64decode(
                        meta_response.json().get("content", "")
                    ).decode()
                    metadata = json.loads(meta_content)
                    item_tags = metadata.get("tags", [])
                    if not any(t in item_tags for t in tags):
                        continue
            
            results.append({
                "name": item_name,
                "category": item_category,
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
        logger.exception(f"[StrixDB] Search failed: {e}")
        return {
            "success": False,
            "error": f"Search failed: {e!s}",
            "results": [],
        }


@register_tool(sandbox_execution=False)
def strixdb_get(
    agent_state: Any,
    category: str,
    name: str,
) -> dict[str, Any]:
    """
    Retrieve a specific item from StrixDB.
    
    Args:
        agent_state: Current agent state
        category: Category of the item
        name: Name of the item
    
    Returns:
        Dictionary with the item content and metadata
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
            "item": None,
        }
    
    try:
        # List files in category to find matching item
        list_url = f"{config['api_base']}/repos/{config['repo']}/contents/{category}"
        list_response = requests.get(
            list_url,
            headers=_get_headers(config["token"]),
            timeout=30,
        )
        
        if list_response.status_code != 200:
            return {
                "success": False,
                "error": f"Category '{category}' not found",
                "item": None,
            }
        
        files = list_response.json()
        sanitized_name = _sanitize_name(name)
        
        # Find matching file
        content_file = None
        meta_file = None
        
        for file in files:
            file_name = file.get("name", "")
            if file_name.startswith(sanitized_name) and not file_name.endswith("_meta.json"):
                content_file = file
            elif file_name == f"{sanitized_name}_meta.json":
                meta_file = file
        
        if not content_file:
            return {
                "success": False,
                "error": f"Item '{name}' not found in category '{category}'",
                "item": None,
            }
        
        # Fetch content
        content_response = requests.get(
            content_file["url"],
            headers=_get_headers(config["token"]),
            timeout=30,
        )
        
        if content_response.status_code != 200:
            return {
                "success": False,
                "error": "Failed to fetch content",
                "item": None,
            }
        
        content_data = content_response.json()
        content = base64.b64decode(content_data.get("content", "")).decode()
        
        # Fetch metadata if available
        metadata = {}
        if meta_file:
            meta_response = requests.get(
                meta_file["url"],
                headers=_get_headers(config["token"]),
                timeout=30,
            )
            if meta_response.status_code == 200:
                meta_data = meta_response.json()
                metadata = json.loads(
                    base64.b64decode(meta_data.get("content", "")).decode()
                )
        
        return {
            "success": True,
            "item": {
                "name": name,
                "category": category,
                "content": content,
                "path": content_file["path"],
                "metadata": metadata,
            },
        }
        
    except requests.RequestException as e:
        logger.exception(f"[StrixDB] Get failed: {e}")
        return {
            "success": False,
            "error": f"Request failed: {e!s}",
            "item": None,
        }


@register_tool(sandbox_execution=False)
def strixdb_list(
    agent_state: Any,
    category: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    List items in StrixDB.
    
    Args:
        agent_state: Current agent state
        category: Optional category to list (None for all categories)
        limit: Maximum number of items to return
    
    Returns:
        Dictionary with list of items
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
            "items": [],
        }
    
    try:
        items = []
        categories_to_list = [category] if category else _get_valid_categories()
        
        for cat in categories_to_list:
            url = f"{config['api_base']}/repos/{config['repo']}/contents/{cat}"
            response = requests.get(
                url,
                headers=_get_headers(config["token"]),
                timeout=30,
            )
            
            if response.status_code == 200:
                files = response.json()
                for file in files:
                    name = file.get("name", "")
                    # Skip metadata files
                    if name.endswith("_meta.json") or name == "README.md":
                        continue
                    
                    items.append({
                        "name": name,
                        "category": cat,
                        "path": file.get("path", ""),
                        "size": file.get("size", 0),
                        "type": file.get("type", "file"),
                    })
            
            if len(items) >= limit:
                break
        
        return {
            "success": True,
            "total": len(items),
            "items": items[:limit],
        }
        
    except requests.RequestException as e:
        logger.exception(f"[StrixDB] List failed: {e}")
        return {
            "success": False,
            "error": f"Request failed: {e!s}",
            "items": [],
        }


@register_tool(sandbox_execution=False)
def strixdb_update(
    agent_state: Any,
    category: str,
    name: str,
    content: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update an existing item in StrixDB.
    
    Args:
        agent_state: Current agent state
        category: Category of the item
        name: Name of the item
        content: New content
        description: Optional new description
        tags: Optional new tags
    
    Returns:
        Dictionary with operation result
    """
    # First get the existing item to preserve metadata
    existing = strixdb_get(agent_state, category, name)
    
    if not existing["success"]:
        return existing
    
    # Preserve existing metadata, update only provided fields
    existing_metadata = existing["item"].get("metadata", {})
    
    return strixdb_save(
        agent_state,
        category=category,
        name=name,
        content=content,
        description=description or existing_metadata.get("description", ""),
        tags=tags or existing_metadata.get("tags", []),
        content_type=existing_metadata.get("content_type", "text"),
    )


@register_tool(sandbox_execution=False)
def strixdb_delete(
    agent_state: Any,
    category: str,
    name: str,
) -> dict[str, Any]:
    """
    Delete an item from StrixDB.
    
    Args:
        agent_state: Current agent state
        category: Category of the item
        name: Name of the item
    
    Returns:
        Dictionary with operation result
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
        }
    
    try:
        # First get the item to find exact path and SHA
        existing = strixdb_get(agent_state, category, name)
        
        if not existing["success"]:
            return existing
        
        path = existing["item"]["path"]
        sanitized_name = _sanitize_name(name)
        meta_path = path.replace(
            path.split("/")[-1],
            f"{sanitized_name}_meta.json"
        )
        
        # Get SHA for content file
        content_url = f"{config['api_base']}/repos/{config['repo']}/contents/{path}"
        content_response = requests.get(
            content_url,
            headers=_get_headers(config["token"]),
            timeout=30,
        )
        
        if content_response.status_code != 200:
            return {
                "success": False,
                "error": "Failed to get file info for deletion",
            }
        
        content_sha = content_response.json().get("sha")
        
        # Delete content file
        delete_response = requests.delete(
            content_url,
            headers=_get_headers(config["token"]),
            json={
                "message": f"[StrixDB] Delete {category}/{name}",
                "sha": content_sha,
                "branch": config["branch"],
            },
            timeout=30,
        )
        
        if delete_response.status_code not in (200, 204):
            return {
                "success": False,
                "error": f"Failed to delete content: {delete_response.status_code}",
            }
        
        # Try to delete metadata file
        meta_url = f"{config['api_base']}/repos/{config['repo']}/contents/{meta_path}"
        meta_response = requests.get(
            meta_url,
            headers=_get_headers(config["token"]),
            timeout=30,
        )
        
        if meta_response.status_code == 200:
            meta_sha = meta_response.json().get("sha")
            requests.delete(
                meta_url,
                headers=_get_headers(config["token"]),
                json={
                    "message": f"[StrixDB] Delete metadata for {category}/{name}",
                    "sha": meta_sha,
                    "branch": config["branch"],
                },
                timeout=30,
            )
        
        return {
            "success": True,
            "message": f"Successfully deleted '{name}' from category '{category}'",
        }
        
    except requests.RequestException as e:
        logger.exception(f"[StrixDB] Delete failed: {e}")
        return {
            "success": False,
            "error": f"Request failed: {e!s}",
        }


@register_tool(sandbox_execution=False)
def strixdb_get_categories(agent_state: Any) -> dict[str, Any]:
    """
    Get all available categories in StrixDB with their descriptions.
    
    Args:
        agent_state: Current agent state
    
    Returns:
        Dictionary with categories information
    """
    config = _get_strixdb_config()
    
    categories = []
    all_categories = _get_valid_categories()
    
    for cat in all_categories:
        desc = CATEGORY_DESCRIPTIONS.get(cat, "Custom category")
        cat_info = {
            "name": cat,
            "description": desc,
            "item_count": 0,
            "is_custom": cat in _dynamic_categories,
        }
        
        # Get item count if StrixDB is configured
        if config["repo"] and config["token"]:
            try:
                url = f"{config['api_base']}/repos/{config['repo']}/contents/{cat}"
                response = requests.get(
                    url,
                    headers=_get_headers(config["token"]),
                    timeout=10,
                )
                if response.status_code == 200:
                    files = response.json()
                    # Count non-metadata files
                    cat_info["item_count"] = sum(
                        1 for f in files 
                        if not f.get("name", "").endswith("_meta.json") 
                        and f.get("name") != "README.md"
                    )
            except requests.RequestException:
                pass
        
        categories.append(cat_info)
    
    return {
        "success": True,
        "categories": categories,
        "total_categories": len(categories),
        "hint": "You can create new categories using strixdb_create_category()",
    }


@register_tool(sandbox_execution=False)
def strixdb_get_stats(agent_state: Any) -> dict[str, Any]:
    """
    Get statistics about the StrixDB repository.
    
    Args:
        agent_state: Current agent state
    
    Returns:
        Dictionary with repository statistics
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
            "stats": None,
        }
    
    try:
        # Get repository info
        url = f"{config['api_base']}/repos/{config['repo']}"
        response = requests.get(
            url,
            headers=_get_headers(config["token"]),
            timeout=30,
        )
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": "Failed to get repository info",
                "stats": None,
            }
        
        repo_data = response.json()
        
        # Count items per category
        category_counts = {}
        total_items = 0
        
        for cat in _get_valid_categories():
            cat_url = f"{config['api_base']}/repos/{config['repo']}/contents/{cat}"
            cat_response = requests.get(
                cat_url,
                headers=_get_headers(config["token"]),
                timeout=10,
            )
            
            if cat_response.status_code == 200:
                files = cat_response.json()
                count = sum(
                    1 for f in files 
                    if not f.get("name", "").endswith("_meta.json")
                    and f.get("name") != "README.md"
                )
                category_counts[cat] = count
                total_items += count
            else:
                category_counts[cat] = 0
        
        return {
            "success": True,
            "stats": {
                "repo_name": config["repo"],
                "branch": config["branch"],
                "total_items": total_items,
                "categories": category_counts,
                "size_kb": repo_data.get("size", 0),
                "last_updated": repo_data.get("updated_at", ""),
                "visibility": repo_data.get("visibility", "private"),
            },
        }
        
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Request failed: {e!s}",
            "stats": None,
        }


@register_tool(sandbox_execution=False)
def strixdb_get_config_status(agent_state: Any) -> dict[str, Any]:
    """
    Get the current StrixDB configuration status.
    
    This is useful for debugging configuration issues.
    
    Args:
        agent_state: Current agent state
    
    Returns:
        Dictionary with configuration status
    """
    config = _get_strixdb_config()
    
    is_configured = bool(config["repo"] and config["token"])
    
    # Test connection if configured
    connection_status = "not_tested"
    if is_configured:
        try:
            url = f"{config['api_base']}/repos/{config['repo']}"
            response = requests.get(
                url,
                headers=_get_headers(config["token"]),
                timeout=10,
            )
            if response.status_code == 200:
                connection_status = "connected"
            elif response.status_code == 404:
                connection_status = "repository_not_found"
            elif response.status_code == 401:
                connection_status = "authentication_failed"
            else:
                connection_status = f"error_{response.status_code}"
        except requests.RequestException as e:
            connection_status = f"connection_error: {e!s}"
    
    return {
        "success": True,
        "configured": is_configured,
        "connection_status": connection_status,
        "repository": config["repo"] if is_configured else None,
        "branch": config["branch"],
        "token_set": bool(config["token"]),
        "setup_instructions": (
            "To configure StrixDB:\n"
            "1. Create a GitHub repository named 'StrixDB'\n"
            "2. Create a GitHub Personal Access Token (PAT) with 'repo' scope\n"
            "3. Add the token as STRIXDB_TOKEN in your repository secrets\n"
            "4. The workflow will automatically pass the token to Strix"
        ) if not is_configured else None,
    }


@register_tool(sandbox_execution=False)
def strixdb_export(
    agent_state: Any,
    category: str | None = None,
    format: str = "json",
) -> dict[str, Any]:
    """
    Export items from StrixDB.
    
    Args:
        agent_state: Current agent state
        category: Optional category to export (None for all)
        format: Export format (json, markdown)
    
    Returns:
        Dictionary with exported data
    """
    list_result = strixdb_list(agent_state, category, limit=1000)
    
    if not list_result["success"]:
        return list_result
    
    exported_items = []
    
    for item in list_result["items"]:
        item_result = strixdb_get(agent_state, item["category"], item["name"])
        if item_result["success"]:
            exported_items.append(item_result["item"])
    
    if format == "markdown":
        # Format as markdown
        md_output = "# StrixDB Export\n\n"
        current_category = None
        
        for item in exported_items:
            if item["category"] != current_category:
                current_category = item["category"]
                md_output += f"\n## {current_category.title()}\n\n"
            
            md_output += f"### {item['name']}\n\n"
            if item.get("metadata", {}).get("description"):
                md_output += f"*{item['metadata']['description']}*\n\n"
            md_output += f"```\n{item['content']}\n```\n\n"
        
        return {
            "success": True,
            "format": "markdown",
            "data": md_output,
            "item_count": len(exported_items),
        }
    
    return {
        "success": True,
        "format": "json",
        "data": exported_items,
        "item_count": len(exported_items),
    }


@register_tool(sandbox_execution=False)
def strixdb_import_item(
    agent_state: Any,
    item_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Import an item to StrixDB.
    
    Args:
        agent_state: Current agent state
        item_data: Dictionary with item data (category, name, content, etc.)
    
    Returns:
        Dictionary with import result
    """
    required_fields = ["category", "name", "content"]
    for field in required_fields:
        if field not in item_data:
            return {
                "success": False,
                "error": f"Missing required field: {field}",
            }
    
    return strixdb_save(
        agent_state,
        category=item_data["category"],
        name=item_data["name"],
        content=item_data["content"],
        description=item_data.get("description", ""),
        tags=item_data.get("tags", []),
        content_type=item_data.get("content_type", "text"),
    )
