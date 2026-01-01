"""
StrixDB Target Tracking System - Comprehensive Target Management

This module provides advanced target tracking capabilities for the AI agent.
It stores COMPREHENSIVE, DETAILED, and UNFILTERED information about each target
scanned, enabling intelligent session continuity across multiple scan sessions.

KEY FEATURES:
- Comprehensive target profiles with all discovered data
- Session management for scan continuity
- Progress tracking to avoid redundant work
- Finding history with full details
- Technology stack tracking
- Endpoint/path discovery tracking
- Credential and authentication info storage
- Infrastructure mapping

IMPORTANT DESIGN PRINCIPLES:
1. Store EVERYTHING useful - be comprehensive and detailed
2. Never lose data between sessions
3. Enable smart continuation without repetition
4. Keep findings unfiltered but reasonably organized
5. Support updates and additions to existing data

Target Structure:
- targets/{target_slug}/
  - profile.json - Main target profile and metadata
  - sessions/ - Individual session data
  - findings/ - Vulnerability findings
  - endpoints.json - Discovered endpoints and paths
  - technologies.json - Tech stack information
  - notes.json - Session notes and observations
"""

from __future__ import annotations

import base64
import hashlib
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


def _sanitize_target_slug(target: str) -> str:
    """
    Create a safe directory-friendly slug from a target identifier.
    Handles URLs, IPs, domains, etc.
    """
    # Remove protocol
    target = re.sub(r'^https?://', '', target)
    # Remove trailing slashes and paths for domain-based slugs
    target = target.split('/')[0]
    # Remove port numbers for cleaner slug
    target = re.sub(r':\d+$', '', target)
    # Replace unsafe characters
    slug = re.sub(r'[^\w\-.]', '_', target)
    # Remove multiple underscores
    slug = re.sub(r'_+', '_', slug)
    # Trim and lowercase
    slug = slug.strip('_').lower()
    
    # Add hash suffix for uniqueness if slug is too generic
    if len(slug) < 3:
        slug = f"{slug}_{hashlib.md5(target.encode()).hexdigest()[:8]}"
    
    return slug


def _generate_session_id() -> str:
    """Generate a unique session ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique = str(uuid.uuid4())[:8]
    return f"session_{timestamp}_{unique}"


def _create_initial_target_profile(
    target: str,
    target_type: str,
    description: str = "",
    scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create the initial target profile structure."""
    now = datetime.now(timezone.utc).isoformat()
    slug = _sanitize_target_slug(target)
    
    return {
        "id": str(uuid.uuid4())[:12],
        "slug": slug,
        "target": target,
        "target_type": target_type,  # web_app, api, domain, ip, repository, network
        "description": description,
        "created_at": now,
        "updated_at": now,
        "last_scan_at": None,
        "total_sessions": 0,
        "status": "initialized",  # initialized, active, paused, completed
        
        # Scope configuration
        "scope": {
            "in_scope": scope or [target],
            "out_of_scope": out_of_scope or [],
        },
        
        # Tags for organization
        "tags": tags or [],
        
        # Summary statistics
        "stats": {
            "total_findings": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
            "endpoints_discovered": 0,
            "technologies_identified": 0,
            "credentials_found": 0,
            "sessions_count": 0,
        },
        
        # Quick access to important data
        "quick_info": {
            "main_technologies": [],
            "confirmed_vulnerabilities": [],
            "key_endpoints": [],
            "authentication_status": "unknown",
            "last_session_summary": "",
        },
        
        # What has been tested (to avoid repetition)
        "tested_areas": {
            "reconnaissance": [],
            "vulnerability_types": [],
            "endpoints_tested": [],
            "payloads_tried": [],
        },
        
        # What still needs to be done
        "pending_work": {
            "high_priority": [],
            "medium_priority": [],
            "low_priority": [],
            "follow_ups": [],
        },
        
        # Session history summary
        "session_history": [],
    }


def _create_session_data(
    session_id: str,
    target_slug: str,
    objective: str = "",
    focus_areas: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new session data structure."""
    now = datetime.now(timezone.utc).isoformat()
    
    return {
        "session_id": session_id,
        "target_slug": target_slug,
        "started_at": now,
        "ended_at": None,
        "duration_minutes": 0,
        "status": "active",  # active, completed, paused, failed
        
        # Session configuration
        "objective": objective,
        "focus_areas": focus_areas or [],
        
        # What was accomplished
        "accomplishments": [],
        
        # Findings discovered in this session
        "findings": [],
        
        # Endpoints discovered/tested in this session
        "endpoints": {
            "discovered": [],
            "tested": [],
            "vulnerable": [],
        },
        
        # Technologies identified in this session
        "technologies": [],
        
        # Commands/tools executed
        "tool_executions": [],
        
        # Notes and observations
        "notes": [],
        
        # What to continue in next session
        "continuation_notes": {
            "immediate_follow_ups": [],
            "promising_leads": [],
            "blocked_by": [],
            "recommendations": [],
        },
        
        # Session metrics
        "metrics": {
            "findings_count": 0,
            "endpoints_discovered": 0,
            "endpoints_tested": 0,
            "tools_used": [],
        },
    }


def _get_or_create_target_file(
    config: dict[str, str],
    target_slug: str,
    file_name: str,
    default_content: dict[str, Any] | list[Any],
) -> tuple[dict[str, Any] | list[Any], str | None]:
    """
    Get existing file content or return default.
    Returns (content, sha) where sha is None if file doesn't exist.
    """
    path = f"targets/{target_slug}/{file_name}"
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


def _save_target_file(
    config: dict[str, str],
    target_slug: str,
    file_name: str,
    content: dict[str, Any] | list[Any],
    sha: str | None = None,
    commit_message: str = "",
) -> bool:
    """Save a file to the target's directory in StrixDB."""
    path = f"targets/{target_slug}/{file_name}"
    url = f"{config['api_base']}/repos/{config['repo']}/contents/{path}"
    
    content_encoded = base64.b64encode(json.dumps(content, indent=2).encode()).decode()
    
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


def _ensure_target_directory(config: dict[str, str], target_slug: str) -> bool:
    """Ensure the target directory exists in StrixDB."""
    readme_path = f"targets/{target_slug}/README.md"
    url = f"{config['api_base']}/repos/{config['repo']}/contents/{readme_path}"
    
    try:
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 200:
            return True  # Already exists
        
        if response.status_code == 404:
            # Create the directory with a README
            readme_content = f"""# Target: {target_slug}

This directory contains comprehensive scan data for target: `{target_slug}`

## Contents

- `profile.json` - Main target profile and metadata
- `sessions/` - Individual session data
- `findings/` - Vulnerability findings
- `endpoints.json` - Discovered endpoints and paths
- `technologies.json` - Technology stack information
- `notes.json` - Session notes and observations

## Auto-generated by StrixDB Target Tracking System
"""
            content_encoded = base64.b64encode(readme_content.encode()).decode()
            
            create_response = requests.put(
                url,
                headers=_get_headers(config["token"]),
                json={
                    "message": f"[StrixDB] Initialize target: {target_slug}",
                    "content": content_encoded,
                    "branch": config["branch"],
                },
                timeout=30,
            )
            
            return create_response.status_code in (200, 201)
        
        return False
        
    except requests.RequestException:
        return False


@register_tool(sandbox_execution=False)
def strixdb_target_init(
    agent_state: Any,
    target: str,
    target_type: str = "web_app",
    description: str = "",
    scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Initialize a new target in StrixDB for comprehensive tracking.
    
    This creates a persistent target profile that will store ALL data
    discovered across all scanning sessions. Call this when starting
    to scan a new target for the first time.
    
    If the target already exists, returns the existing profile data
    along with a summary of previous work to help avoid repetition.
    
    Args:
        agent_state: Current agent state
        target: The target identifier (URL, domain, IP, repo URL, etc.)
        target_type: Type of target - web_app, api, domain, ip, repository, network
        description: Description of the target and engagement
        scope: List of in-scope items (URLs, domains, IPs)
        out_of_scope: List of out-of-scope items
        tags: Tags for categorization
    
    Returns:
        Dictionary with target profile and previous session info if exists
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured. Ensure STRIXDB_TOKEN is set.",
            "target": None,
        }
    
    target_slug = _sanitize_target_slug(target)
    
    # Check if target already exists
    existing_profile, existing_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if existing_profile and existing_sha:
        # Target exists - return existing data with guidance
        return {
            "success": True,
            "message": f"Target '{target_slug}' already exists. Use existing data to continue.",
            "is_new": False,
            "target": {
                "slug": target_slug,
                "profile": existing_profile,
                "previous_sessions_count": existing_profile.get("total_sessions", 0),
                "last_scan_at": existing_profile.get("last_scan_at"),
                "stats": existing_profile.get("stats", {}),
                "quick_info": existing_profile.get("quick_info", {}),
                "tested_areas": existing_profile.get("tested_areas", {}),
                "pending_work": existing_profile.get("pending_work", {}),
            },
            "continuation_guidance": (
                "This target has been scanned before. Review the 'tested_areas' to avoid "
                "repeating work. Check 'pending_work' for items that need follow-up. "
                "Start a new session with strixdb_target_session_start() to continue."
            ),
        }
    
    # Create new target
    if not _ensure_target_directory(config, target_slug):
        return {
            "success": False,
            "error": f"Failed to create target directory for '{target_slug}'",
            "target": None,
        }
    
    # Create initial profile
    profile = _create_initial_target_profile(
        target=target,
        target_type=target_type,
        description=description,
        scope=scope,
        out_of_scope=out_of_scope,
        tags=tags,
    )
    
    if not _save_target_file(
        config,
        target_slug,
        "profile.json",
        profile,
        commit_message=f"[StrixDB] Initialize target profile: {target_slug}",
    ):
        return {
            "success": False,
            "error": f"Failed to save target profile for '{target_slug}'",
            "target": None,
        }
    
    # Create empty data files
    empty_structures = {
        "endpoints.json": {"discovered": [], "tested": [], "vulnerable": []},
        "technologies.json": {"identified": [], "versions": {}},
        "notes.json": {"entries": []},
        "findings.json": {"vulnerabilities": [], "informational": []},
    }
    
    for file_name, content in empty_structures.items():
        _save_target_file(
            config,
            target_slug,
            file_name,
            content,
            commit_message=f"[StrixDB] Initialize {file_name} for {target_slug}",
        )
    
    logger.info(f"[StrixDB] Initialized new target: {target_slug}")
    
    return {
        "success": True,
        "message": f"Successfully initialized target '{target_slug}'",
        "is_new": True,
        "target": {
            "slug": target_slug,
            "profile": profile,
            "previous_sessions_count": 0,
        },
        "next_step": (
            "Target initialized! Call strixdb_target_session_start() to begin "
            "your first scan session and start tracking your work."
        ),
    }


@register_tool(sandbox_execution=False)
def strixdb_target_session_start(
    agent_state: Any,
    target: str,
    objective: str = "",
    focus_areas: list[str] | None = None,
    timeframe_minutes: int = 60,
) -> dict[str, Any]:
    """
    Start a new scan session for a target.
    
    Call this at the beginning of each scanning session. It will:
    1. Load all previous data about the target
    2. Provide a summary of what has been tested/found
    3. Create a new session to track this session's work
    4. Return guidance on what to focus on
    
    Args:
        agent_state: Current agent state
        target: Target identifier (will be matched to existing target)
        objective: What you aim to accomplish in this session
        focus_areas: Specific areas to focus on (e.g., ["auth", "api", "file_upload"])
        timeframe_minutes: Expected session duration for planning
    
    Returns:
        Dictionary with session info, target summary, and continuation guidance
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {
            "success": False,
            "error": "StrixDB not configured",
            "session": None,
        }
    
    target_slug = _sanitize_target_slug(target)
    
    # Load existing profile
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if not profile or not profile_sha:
        return {
            "success": False,
            "error": f"Target '{target_slug}' not found. Initialize it first with strixdb_target_init()",
            "session": None,
        }
    
    # Load supplementary data
    endpoints, _ = _get_or_create_target_file(
        config, target_slug, "endpoints.json",
        {"discovered": [], "tested": [], "vulnerable": []}
    )
    technologies, _ = _get_or_create_target_file(
        config, target_slug, "technologies.json",
        {"identified": [], "versions": {}}
    )
    findings, _ = _get_or_create_target_file(
        config, target_slug, "findings.json",
        {"vulnerabilities": [], "informational": []}
    )
    notes, _ = _get_or_create_target_file(
        config, target_slug, "notes.json",
        {"entries": []}
    )
    
    # Create new session
    session_id = _generate_session_id()
    session_data = _create_session_data(
        session_id=session_id,
        target_slug=target_slug,
        objective=objective,
        focus_areas=focus_areas,
    )
    
    # Save session
    if not _save_target_file(
        config,
        target_slug,
        f"sessions/{session_id}.json",
        session_data,
        commit_message=f"[StrixDB] Start session {session_id} for {target_slug}",
    ):
        return {
            "success": False,
            "error": "Failed to create session",
            "session": None,
        }
    
    # Update profile with session start
    profile["status"] = "active"
    profile["last_scan_at"] = datetime.now(timezone.utc).isoformat()
    profile["total_sessions"] = profile.get("total_sessions", 0) + 1
    profile["stats"]["sessions_count"] = profile["total_sessions"]
    
    _save_target_file(
        config,
        target_slug,
        "profile.json",
        profile,
        sha=profile_sha,
        commit_message=f"[StrixDB] Update profile - session {session_id} started",
    )
    
    # Build comprehensive summary for the AI
    tested_areas = profile.get("tested_areas", {})
    pending_work = profile.get("pending_work", {})
    quick_info = profile.get("quick_info", {})
    
    # Generate smart recommendations
    recommendations = []
    if pending_work.get("high_priority"):
        recommendations.append(f"HIGH PRIORITY: {', '.join(pending_work['high_priority'][:3])}")
    if pending_work.get("follow_ups"):
        recommendations.append(f"Follow-ups from last session: {', '.join(pending_work['follow_ups'][:3])}")
    if not tested_areas.get("vulnerability_types"):
        recommendations.append("No vulnerability testing recorded yet - start with recon and common vulns")
    
    logger.info(f"[StrixDB] Started session {session_id} for target {target_slug}")
    
    return {
        "success": True,
        "message": f"Session '{session_id}' started for target '{target_slug}'",
        "session": {
            "session_id": session_id,
            "target_slug": target_slug,
            "objective": objective,
            "focus_areas": focus_areas,
            "timeframe_minutes": timeframe_minutes,
        },
        "target_summary": {
            "previous_sessions": profile.get("total_sessions", 1) - 1,
            "total_findings": profile.get("stats", {}).get("total_findings", 0),
            "severity_breakdown": {
                "critical": profile.get("stats", {}).get("critical", 0),
                "high": profile.get("stats", {}).get("high", 0),
                "medium": profile.get("stats", {}).get("medium", 0),
                "low": profile.get("stats", {}).get("low", 0),
            },
            "endpoints_discovered": len(endpoints.get("discovered", [])),
            "technologies": technologies.get("identified", [])[:10],
            "confirmed_vulns": quick_info.get("confirmed_vulnerabilities", []),
            "key_endpoints": quick_info.get("key_endpoints", [])[:10],
        },
        "previous_work": {
            "tested_vulnerability_types": tested_areas.get("vulnerability_types", []),
            "tested_endpoints_count": len(tested_areas.get("endpoints_tested", [])),
            "recon_completed": tested_areas.get("reconnaissance", []),
        },
        "pending_work": pending_work,
        "recommendations": recommendations,
        "continuation_guidance": (
            "Session started! As you work, use:\n"
            "- strixdb_target_add_finding() to record vulnerabilities\n"
            "- strixdb_target_add_endpoint() to track discovered endpoints\n"
            "- strixdb_target_add_note() for observations\n"
            "- strixdb_target_update_progress() to mark tested areas\n"
            "- strixdb_target_session_end() when finished\n\n"
            "IMPORTANT: Store EVERYTHING useful - be comprehensive!"
        ),
    }


@register_tool(sandbox_execution=False)
def strixdb_target_session_end(
    agent_state: Any,
    target: str,
    session_id: str,
    summary: str,
    accomplishments: list[str] | None = None,
    immediate_follow_ups: list[str] | None = None,
    promising_leads: list[str] | None = None,
    blocked_by: list[str] | None = None,
    recommendations: list[str] | None = None,
) -> dict[str, Any]:
    """
    End a scan session and save comprehensive session data.
    
    Call this when finishing a scanning session. Provide detailed
    continuation notes so the next session can pick up efficiently.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: The session ID to end
        summary: Comprehensive summary of what was done
        accomplishments: List of things accomplished in this session
        immediate_follow_ups: Things to do immediately in next session
        promising_leads: Promising areas that need more investigation
        blocked_by: Things that blocked progress
        recommendations: Recommendations for next session
    
    Returns:
        Dictionary with session summary and guidance
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    
    # Load session
    session_data, session_sha = _get_or_create_target_file(
        config, target_slug, f"sessions/{session_id}.json", {}
    )
    
    if not session_data or not session_sha:
        return {
            "success": False,
            "error": f"Session '{session_id}' not found for target '{target_slug}'",
        }
    
    # Load profile
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    # Update session data
    now = datetime.now(timezone.utc)
    started_at = datetime.fromisoformat(session_data.get("started_at", now.isoformat()).replace('Z', '+00:00'))
    duration = int((now - started_at).total_seconds() / 60)
    
    session_data["ended_at"] = now.isoformat()
    session_data["duration_minutes"] = duration
    session_data["status"] = "completed"
    session_data["accomplishments"] = accomplishments or []
    session_data["continuation_notes"] = {
        "immediate_follow_ups": immediate_follow_ups or [],
        "promising_leads": promising_leads or [],
        "blocked_by": blocked_by or [],
        "recommendations": recommendations or [],
    }
    
    # Save session
    _save_target_file(
        config,
        target_slug,
        f"sessions/{session_id}.json",
        session_data,
        sha=session_sha,
        commit_message=f"[StrixDB] End session {session_id}",
    )
    
    # Update profile
    if profile and profile_sha:
        profile["status"] = "paused"
        profile["updated_at"] = now.isoformat()
        profile["quick_info"]["last_session_summary"] = summary
        
        # Update pending work
        if immediate_follow_ups:
            existing_high = profile.get("pending_work", {}).get("high_priority", [])
            profile["pending_work"]["high_priority"] = list(set(existing_high + immediate_follow_ups))[:20]
        if promising_leads:
            existing_medium = profile.get("pending_work", {}).get("medium_priority", [])
            profile["pending_work"]["medium_priority"] = list(set(existing_medium + promising_leads))[:20]
        if recommendations:
            profile["pending_work"]["follow_ups"] = recommendations[:10]
        
        # Add to session history
        session_summary = {
            "session_id": session_id,
            "date": now.isoformat(),
            "duration_minutes": duration,
            "summary": summary[:500],
            "findings_count": session_data.get("metrics", {}).get("findings_count", 0),
        }
        history = profile.get("session_history", [])
        history.append(session_summary)
        profile["session_history"] = history[-20:]  # Keep last 20 sessions
        
        _save_target_file(
            config,
            target_slug,
            "profile.json",
            profile,
            sha=profile_sha,
            commit_message=f"[StrixDB] Update profile after session {session_id}",
        )
    
    logger.info(f"[StrixDB] Ended session {session_id} for target {target_slug}")
    
    return {
        "success": True,
        "message": f"Session '{session_id}' ended successfully",
        "session_summary": {
            "session_id": session_id,
            "duration_minutes": duration,
            "accomplishments": accomplishments,
            "findings_recorded": session_data.get("metrics", {}).get("findings_count", 0),
            "endpoints_discovered": session_data.get("metrics", {}).get("endpoints_discovered", 0),
        },
        "continuation_saved": {
            "immediate_follow_ups": immediate_follow_ups,
            "promising_leads": promising_leads,
            "blocked_by": blocked_by,
            "recommendations": recommendations,
        },
        "hint": (
            "Session data saved! Next time you scan this target, use "
            "strixdb_target_session_start() to load all context and continue efficiently."
        ),
    }


@register_tool(sandbox_execution=False)
def strixdb_target_add_finding(
    agent_state: Any,
    target: str,
    session_id: str,
    title: str,
    severity: str,
    vulnerability_type: str,
    description: str,
    affected_endpoint: str = "",
    proof_of_concept: str = "",
    steps_to_reproduce: list[str] | None = None,
    impact: str = "",
    remediation: str = "",
    references: list[str] | None = None,
    tags: list[str] | None = None,
    additional_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add a vulnerability finding to the target.
    
    Store COMPREHENSIVE finding data. Be detailed - include everything
    that could be useful for reporting or follow-up exploitation.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: Current session ID
        title: Clear, descriptive title
        severity: critical, high, medium, low, info
        vulnerability_type: e.g., sqli, xss, idor, ssrf, rce, auth_bypass
        description: Detailed description of the vulnerability
        affected_endpoint: The vulnerable endpoint/parameter
        proof_of_concept: Working PoC code or payload
        steps_to_reproduce: Step-by-step reproduction steps
        impact: Business/security impact
        remediation: How to fix it
        references: Related CVEs, articles, etc.
        tags: Categorization tags
        additional_data: Any extra data (request/response, screenshots paths, etc.)
    
    Returns:
        Dictionary with saved finding info
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    now = datetime.now(timezone.utc).isoformat()
    
    finding_id = f"finding_{str(uuid.uuid4())[:8]}"
    
    finding = {
        "id": finding_id,
        "session_id": session_id,
        "title": title,
        "severity": severity.lower(),
        "vulnerability_type": vulnerability_type,
        "description": description,
        "affected_endpoint": affected_endpoint,
        "proof_of_concept": proof_of_concept,
        "steps_to_reproduce": steps_to_reproduce or [],
        "impact": impact,
        "remediation": remediation,
        "references": references or [],
        "tags": tags or [],
        "additional_data": additional_data or {},
        "created_at": now,
        "status": "confirmed",  # confirmed, potential, false_positive
        "verified": True,
    }
    
    # Load existing findings
    findings, findings_sha = _get_or_create_target_file(
        config, target_slug, "findings.json",
        {"vulnerabilities": [], "informational": []}
    )
    
    if severity.lower() == "info":
        findings["informational"].append(finding)
    else:
        findings["vulnerabilities"].append(finding)
    
    # Save findings
    if not _save_target_file(
        config,
        target_slug,
        "findings.json",
        findings,
        sha=findings_sha,
        commit_message=f"[StrixDB] Add finding: {title[:50]}",
    ):
        return {"success": False, "error": "Failed to save finding"}
    
    # Update profile stats
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if profile and profile_sha:
        stats = profile.get("stats", {})
        stats["total_findings"] = stats.get("total_findings", 0) + 1
        stats[severity.lower()] = stats.get(severity.lower(), 0) + 1
        profile["stats"] = stats
        
        # Update quick info
        if severity.lower() in ["critical", "high"]:
            confirmed = profile.get("quick_info", {}).get("confirmed_vulnerabilities", [])
            confirmed.append(f"{severity.upper()}: {title}")
            profile["quick_info"]["confirmed_vulnerabilities"] = confirmed[-10:]
        
        # Mark vulnerability type as tested
        tested = profile.get("tested_areas", {}).get("vulnerability_types", [])
        if vulnerability_type not in tested:
            tested.append(vulnerability_type)
            profile["tested_areas"]["vulnerability_types"] = tested
        
        _save_target_file(
            config,
            target_slug,
            "profile.json",
            profile,
            sha=profile_sha,
            commit_message=f"[StrixDB] Update stats for finding: {finding_id}",
        )
    
    # Update session metrics
    session_data, session_sha = _get_or_create_target_file(
        config, target_slug, f"sessions/{session_id}.json", {}
    )
    
    if session_data and session_sha:
        session_data["findings"].append({
            "id": finding_id,
            "title": title,
            "severity": severity,
        })
        session_data["metrics"]["findings_count"] = len(session_data["findings"])
        
        _save_target_file(
            config,
            target_slug,
            f"sessions/{session_id}.json",
            session_data,
            sha=session_sha,
            commit_message=f"[StrixDB] Update session with finding: {finding_id}",
        )
    
    logger.info(f"[StrixDB] Added finding '{title}' ({severity}) for {target_slug}")
    
    return {
        "success": True,
        "message": f"Finding '{title}' saved successfully",
        "finding": {
            "id": finding_id,
            "title": title,
            "severity": severity,
            "vulnerability_type": vulnerability_type,
        },
    }


@register_tool(sandbox_execution=False)
def strixdb_target_add_endpoint(
    agent_state: Any,
    target: str,
    session_id: str,
    endpoint: str,
    method: str = "GET",
    parameters: list[str] | None = None,
    auth_required: bool = False,
    tested: bool = False,
    vulnerable: bool = False,
    notes: str = "",
    technologies: list[str] | None = None,
) -> dict[str, Any]:
    """
    Add a discovered endpoint to the target.
    
    Track ALL endpoints discovered during scanning. This helps avoid
    re-discovering the same endpoints and provides a comprehensive map.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: Current session ID
        endpoint: The endpoint path (e.g., /api/users, /admin/login)
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        parameters: List of parameters (query, body, path params)
        auth_required: Whether authentication is required
        tested: Whether this endpoint has been tested for vulns
        vulnerable: Whether vulnerabilities were found
        notes: Any relevant notes about this endpoint
        technologies: Technologies/frameworks detected at this endpoint
    
    Returns:
        Dictionary with saved endpoint info
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    now = datetime.now(timezone.utc).isoformat()
    
    endpoint_data = {
        "endpoint": endpoint,
        "method": method.upper(),
        "parameters": parameters or [],
        "auth_required": auth_required,
        "tested": tested,
        "vulnerable": vulnerable,
        "notes": notes,
        "technologies": technologies or [],
        "discovered_at": now,
        "discovered_in_session": session_id,
    }
    
    # Load existing endpoints
    endpoints, endpoints_sha = _get_or_create_target_file(
        config, target_slug, "endpoints.json",
        {"discovered": [], "tested": [], "vulnerable": []}
    )
    
    # Check if endpoint already exists
    existing = [e for e in endpoints.get("discovered", []) 
                if e.get("endpoint") == endpoint and e.get("method") == method.upper()]
    
    if existing:
        # Update existing endpoint
        for i, e in enumerate(endpoints["discovered"]):
            if e.get("endpoint") == endpoint and e.get("method") == method.upper():
                # Merge data
                e.update({k: v for k, v in endpoint_data.items() if v})
                endpoints["discovered"][i] = e
                break
    else:
        endpoints["discovered"].append(endpoint_data)
    
    # Update tested/vulnerable lists
    endpoint_key = f"{method.upper()} {endpoint}"
    if tested and endpoint_key not in endpoints.get("tested", []):
        endpoints.setdefault("tested", []).append(endpoint_key)
    if vulnerable and endpoint_key not in endpoints.get("vulnerable", []):
        endpoints.setdefault("vulnerable", []).append(endpoint_key)
    
    # Save endpoints
    if not _save_target_file(
        config,
        target_slug,
        "endpoints.json",
        endpoints,
        sha=endpoints_sha,
        commit_message=f"[StrixDB] Add/update endpoint: {method} {endpoint}",
    ):
        return {"success": False, "error": "Failed to save endpoint"}
    
    # Update profile stats
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if profile and profile_sha:
        profile["stats"]["endpoints_discovered"] = len(endpoints.get("discovered", []))
        
        # Update key endpoints in quick info
        if vulnerable or auth_required or notes:
            key_endpoints = profile.get("quick_info", {}).get("key_endpoints", [])
            if endpoint_key not in key_endpoints:
                key_endpoints.append(endpoint_key)
                profile["quick_info"]["key_endpoints"] = key_endpoints[-20:]
        
        _save_target_file(
            config,
            target_slug,
            "profile.json",
            profile,
            sha=profile_sha,
            commit_message=f"[StrixDB] Update stats for endpoint",
        )
    
    # Update session
    session_data, session_sha = _get_or_create_target_file(
        config, target_slug, f"sessions/{session_id}.json", {}
    )
    
    if session_data and session_sha:
        if not existing:
            session_endpoints = session_data.get("endpoints", {})
            session_endpoints.setdefault("discovered", []).append(endpoint_key)
            session_data["endpoints"] = session_endpoints
            session_data["metrics"]["endpoints_discovered"] = len(session_endpoints.get("discovered", []))
        
        if tested:
            session_data["endpoints"].setdefault("tested", []).append(endpoint_key)
            session_data["metrics"]["endpoints_tested"] = len(session_data["endpoints"].get("tested", []))
        
        _save_target_file(
            config,
            target_slug,
            f"sessions/{session_id}.json",
            session_data,
            sha=session_sha,
            commit_message=f"[StrixDB] Update session with endpoint",
        )
    
    return {
        "success": True,
        "message": f"Endpoint '{method} {endpoint}' saved",
        "endpoint": endpoint_data,
        "is_new": not bool(existing),
    }


@register_tool(sandbox_execution=False)
def strixdb_target_add_note(
    agent_state: Any,
    target: str,
    session_id: str,
    note: str,
    category: str = "observation",
    priority: str = "normal",
    related_to: str = "",
) -> dict[str, Any]:
    """
    Add a note or observation about the target.
    
    Store observations, interesting behaviors, potential leads, and anything
    else worth remembering. Be comprehensive!
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: Current session ID
        note: The note content - be detailed!
        category: observation, lead, behavior, config, credential, other
        priority: high, normal, low
        related_to: Related finding/endpoint if applicable
    
    Returns:
        Dictionary confirming note was saved
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    now = datetime.now(timezone.utc).isoformat()
    
    note_entry = {
        "id": f"note_{str(uuid.uuid4())[:8]}",
        "session_id": session_id,
        "content": note,
        "category": category,
        "priority": priority,
        "related_to": related_to,
        "created_at": now,
    }
    
    # Load existing notes
    notes, notes_sha = _get_or_create_target_file(
        config, target_slug, "notes.json",
        {"entries": []}
    )
    
    notes["entries"].append(note_entry)
    
    # Keep notes manageable - max 500 entries
    if len(notes["entries"]) > 500:
        notes["entries"] = notes["entries"][-500:]
    
    if not _save_target_file(
        config,
        target_slug,
        "notes.json",
        notes,
        sha=notes_sha,
        commit_message=f"[StrixDB] Add note: {note[:50]}...",
    ):
        return {"success": False, "error": "Failed to save note"}
    
    # Add to session notes
    session_data, session_sha = _get_or_create_target_file(
        config, target_slug, f"sessions/{session_id}.json", {}
    )
    
    if session_data and session_sha:
        session_data.setdefault("notes", []).append({
            "id": note_entry["id"],
            "content": note[:200],
            "category": category,
        })
        
        _save_target_file(
            config,
            target_slug,
            f"sessions/{session_id}.json",
            session_data,
            sha=session_sha,
            commit_message=f"[StrixDB] Update session with note",
        )
    
    return {
        "success": True,
        "message": "Note saved",
        "note_id": note_entry["id"],
    }


@register_tool(sandbox_execution=False)
def strixdb_target_update_progress(
    agent_state: Any,
    target: str,
    session_id: str,
    recon_completed: list[str] | None = None,
    vuln_types_tested: list[str] | None = None,
    endpoints_tested: list[str] | None = None,
    tools_used: list[str] | None = None,
    add_high_priority: list[str] | None = None,
    add_medium_priority: list[str] | None = None,
    remove_completed: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update the target's progress tracking.
    
    Call this periodically to track what areas have been tested,
    what's still pending, and update priorities based on findings.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: Current session ID
        recon_completed: Recon tasks completed (subdomain_enum, port_scan, tech_detect, etc.)
        vuln_types_tested: Vulnerability types tested (sqli, xss, idor, ssrf, etc.)
        endpoints_tested: Specific endpoints that have been tested
        tools_used: Tools used in this session
        add_high_priority: New high priority items to add
        add_medium_priority: New medium priority items to add
        remove_completed: Items to remove from pending (completed)
    
    Returns:
        Dictionary with updated progress
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    
    # Load profile
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if not profile or not profile_sha:
        return {"success": False, "error": f"Target '{target_slug}' not found"}
    
    # Update tested areas
    tested = profile.get("tested_areas", {
        "reconnaissance": [],
        "vulnerability_types": [],
        "endpoints_tested": [],
        "payloads_tried": [],
    })
    
    if recon_completed:
        tested["reconnaissance"] = list(set(tested.get("reconnaissance", []) + recon_completed))
    if vuln_types_tested:
        tested["vulnerability_types"] = list(set(tested.get("vulnerability_types", []) + vuln_types_tested))
    if endpoints_tested:
        current = tested.get("endpoints_tested", [])
        tested["endpoints_tested"] = list(set(current + endpoints_tested))[-200:]  # Keep last 200
    
    profile["tested_areas"] = tested
    
    # Update pending work
    pending = profile.get("pending_work", {
        "high_priority": [],
        "medium_priority": [],
        "low_priority": [],
        "follow_ups": [],
    })
    
    if add_high_priority:
        pending["high_priority"] = list(set(pending.get("high_priority", []) + add_high_priority))[:20]
    if add_medium_priority:
        pending["medium_priority"] = list(set(pending.get("medium_priority", []) + add_medium_priority))[:20]
    if remove_completed:
        for item in remove_completed:
            for key in pending:
                if item in pending[key]:
                    pending[key].remove(item)
    
    profile["pending_work"] = pending
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if not _save_target_file(
        config,
        target_slug,
        "profile.json",
        profile,
        sha=profile_sha,
        commit_message=f"[StrixDB] Update progress for {target_slug}",
    ):
        return {"success": False, "error": "Failed to update progress"}
    
    # Update session tools used
    if tools_used:
        session_data, session_sha = _get_or_create_target_file(
            config, target_slug, f"sessions/{session_id}.json", {}
        )
        
        if session_data and session_sha:
            current_tools = session_data.get("metrics", {}).get("tools_used", [])
            session_data["metrics"]["tools_used"] = list(set(current_tools + tools_used))
            
            _save_target_file(
                config,
                target_slug,
                f"sessions/{session_id}.json",
                session_data,
                sha=session_sha,
                commit_message=f"[StrixDB] Update session tools used",
            )
    
    return {
        "success": True,
        "message": "Progress updated",
        "tested_areas": tested,
        "pending_work": pending,
    }


@register_tool(sandbox_execution=False)
def strixdb_target_get(
    agent_state: Any,
    target: str,
    include_findings: bool = True,
    include_endpoints: bool = True,
    include_notes: bool = False,
    include_session_history: bool = True,
) -> dict[str, Any]:
    """
    Get comprehensive data about a target.
    
    Retrieve all stored data about a target for review or continuation.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        include_findings: Include all findings
        include_endpoints: Include all endpoints
        include_notes: Include all notes (can be verbose)
        include_session_history: Include session summaries
    
    Returns:
        Dictionary with comprehensive target data
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    
    # Load profile
    profile, _ = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if not profile:
        return {
            "success": False,
            "error": f"Target '{target_slug}' not found",
            "target": None,
        }
    
    result = {
        "success": True,
        "target": {
            "slug": target_slug,
            "profile": profile,
        },
    }
    
    if include_findings:
        findings, _ = _get_or_create_target_file(
            config, target_slug, "findings.json",
            {"vulnerabilities": [], "informational": []}
        )
        result["target"]["findings"] = findings
    
    if include_endpoints:
        endpoints, _ = _get_or_create_target_file(
            config, target_slug, "endpoints.json",
            {"discovered": [], "tested": [], "vulnerable": []}
        )
        result["target"]["endpoints"] = endpoints
    
    if include_notes:
        notes, _ = _get_or_create_target_file(
            config, target_slug, "notes.json",
            {"entries": []}
        )
        result["target"]["notes"] = notes
    
    if include_session_history:
        result["target"]["session_history"] = profile.get("session_history", [])
    
    return result


@register_tool(sandbox_execution=False)
def strixdb_target_list(
    agent_state: Any,
    limit: int = 50,
    include_stats: bool = True,
) -> dict[str, Any]:
    """
    List all targets in StrixDB.
    
    Get a summary of all targets that have been scanned.
    
    Args:
        agent_state: Current agent state
        limit: Maximum number of targets to return
        include_stats: Include summary statistics for each target
    
    Returns:
        Dictionary with list of targets
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured", "targets": []}
    
    try:
        # List contents of targets directory
        url = f"{config['api_base']}/repos/{config['repo']}/contents/targets"
        response = requests.get(url, headers=_get_headers(config["token"]), timeout=30)
        
        if response.status_code == 404:
            return {"success": True, "targets": [], "message": "No targets found"}
        
        if response.status_code != 200:
            return {"success": False, "error": f"Failed to list targets: {response.status_code}", "targets": []}
        
        items = response.json()
        targets = []
        
        for item in items[:limit]:
            if item.get("type") == "dir":
                target_slug = item.get("name")
                
                target_info = {
                    "slug": target_slug,
                }
                
                if include_stats:
                    profile, _ = _get_or_create_target_file(
                        config, target_slug, "profile.json", {}
                    )
                    if profile:
                        target_info.update({
                            "target": profile.get("target", target_slug),
                            "target_type": profile.get("target_type", "unknown"),
                            "status": profile.get("status", "unknown"),
                            "total_sessions": profile.get("total_sessions", 0),
                            "last_scan_at": profile.get("last_scan_at"),
                            "stats": profile.get("stats", {}),
                        })
                
                targets.append(target_info)
        
        return {
            "success": True,
            "targets": targets,
            "total": len(targets),
        }
        
    except requests.RequestException as e:
        return {"success": False, "error": f"Request failed: {e}", "targets": []}


@register_tool(sandbox_execution=False)
def strixdb_target_add_technology(
    agent_state: Any,
    target: str,
    session_id: str,
    technology: str,
    version: str = "",
    confidence: str = "high",
    detected_at: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """
    Add a detected technology to the target profile.
    
    Track all technologies, frameworks, servers, and libraries identified.
    
    Args:
        agent_state: Current agent state
        target: Target identifier
        session_id: Current session ID
        technology: Technology name (e.g., nginx, WordPress, React, PHP)
        version: Version if known
        confidence: Detection confidence - high, medium, low
        detected_at: Where it was detected (header, response, etc.)
        notes: Additional notes
    
    Returns:
        Dictionary confirming technology was saved
    """
    config = _get_strixdb_config()
    
    if not config["repo"] or not config["token"]:
        return {"success": False, "error": "StrixDB not configured"}
    
    target_slug = _sanitize_target_slug(target)
    now = datetime.now(timezone.utc).isoformat()
    
    tech_entry = {
        "technology": technology,
        "version": version,
        "confidence": confidence,
        "detected_at": detected_at,
        "notes": notes,
        "session_id": session_id,
        "discovered_at": now,
    }
    
    # Load existing technologies
    technologies, tech_sha = _get_or_create_target_file(
        config, target_slug, "technologies.json",
        {"identified": [], "versions": {}}
    )
    
    # Check if already exists
    existing = [t for t in technologies.get("identified", []) 
                if t.get("technology", "").lower() == technology.lower()]
    
    if existing:
        # Update version if new one is more specific
        for i, t in enumerate(technologies["identified"]):
            if t.get("technology", "").lower() == technology.lower():
                if version and (not t.get("version") or len(version) > len(t.get("version", ""))):
                    t["version"] = version
                if notes:
                    t["notes"] = notes
                technologies["identified"][i] = t
                break
    else:
        technologies["identified"].append(tech_entry)
    
    # Update versions dict
    if version:
        technologies["versions"][technology] = version
    
    if not _save_target_file(
        config,
        target_slug,
        "technologies.json",
        technologies,
        sha=tech_sha,
        commit_message=f"[StrixDB] Add technology: {technology}",
    ):
        return {"success": False, "error": "Failed to save technology"}
    
    # Update profile quick info
    profile, profile_sha = _get_or_create_target_file(
        config, target_slug, "profile.json", {}
    )
    
    if profile and profile_sha:
        main_techs = profile.get("quick_info", {}).get("main_technologies", [])
        if technology not in main_techs:
            main_techs.append(technology)
            profile["quick_info"]["main_technologies"] = main_techs[-15:]
        profile["stats"]["technologies_identified"] = len(technologies.get("identified", []))
        
        _save_target_file(
            config,
            target_slug,
            "profile.json",
            profile,
            sha=profile_sha,
            commit_message=f"[StrixDB] Update profile for technology: {technology}",
        )
    
    # Update session
    session_data, session_sha = _get_or_create_target_file(
        config, target_slug, f"sessions/{session_id}.json", {}
    )
    
    if session_data and session_sha:
        session_techs = session_data.get("technologies", [])
        if technology not in session_techs:
            session_techs.append(technology)
            session_data["technologies"] = session_techs
        
        _save_target_file(
            config,
            target_slug,
            f"sessions/{session_id}.json",
            session_data,
            sha=session_sha,
            commit_message=f"[StrixDB] Update session with technology",
        )
    
    return {
        "success": True,
        "message": f"Technology '{technology}' saved",
        "technology": tech_entry,
        "is_new": not bool(existing),
    }
