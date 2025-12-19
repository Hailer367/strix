"""Multi-Agent Collaboration Protocol Actions.

Provides tools for coordinated testing between multiple AI agents:
- Claim System: Prevent duplicate testing effort
- Finding Sharing: Share vulnerabilities for chaining opportunities
- Work Queue: Central queue for endpoints/parameters to test
- Help Requests: Request specialized assistance from other agents
"""

import logging
import threading
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from strix.tools.registry import register_tool


logger = logging.getLogger(__name__)

# Thread-safe locks for shared state
_claims_lock = threading.RLock()
_findings_lock = threading.RLock()
_queue_lock = threading.RLock()
_help_lock = threading.RLock()

# Global state for collaboration
# Claims: endpoint/parameter -> agent claiming it
_claims: dict[str, dict[str, Any]] = {}

# Shared findings between agents
_shared_findings: list[dict[str, Any]] = []

# Work queue for coordinated testing
_work_queue: list[dict[str, Any]] = []

# Help requests
_help_requests: list[dict[str, Any]] = []

# Message broadcast history
_broadcast_history: list[dict[str, Any]] = []


def _generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}_{uuid4().hex[:8]}"


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(UTC).isoformat()


# =============================================================================
# CLAIM SYSTEM
# Prevent duplicate work by claiming endpoints/parameters for testing
# =============================================================================


@register_tool(sandbox_execution=False)
def claim_target(
    agent_state: Any,
    target: str,
    test_type: str,
    description: str | None = None,
    estimated_duration_minutes: int = 30,
) -> dict[str, Any]:
    """Claim an endpoint/parameter for testing to prevent duplicate work.

    Before testing an endpoint or parameter, claim it so other agents know
    you're working on it and won't duplicate your effort.

    Args:
        target: The target to claim (URL path, parameter, or feature)
                Examples: "/api/users", "id parameter on /items", "/login SQLi"
        test_type: Type of test being performed
                   Examples: "sqli", "xss", "auth_bypass", "idor", "ssrf", "recon"
        description: Optional detailed description of what you're testing
        estimated_duration_minutes: How long you expect the test to take (default: 30)

    Returns:
        Dictionary containing:
        - success: Whether the claim was successful
        - claim_id: Unique ID for the claim (if successful)
        - conflict: Information about existing claim (if failed)
        - message: Status message
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        # Create claim key
        claim_key = f"{target}:{test_type}".lower()

        with _claims_lock:
            # Check if already claimed
            if claim_key in _claims:
                existing_claim = _claims[claim_key]

                # Check if claim is expired (past estimated duration)
                claimed_at = existing_claim["claimed_at"].replace("Z", "+00:00")
                claim_time = datetime.fromisoformat(claimed_at)
                elapsed_minutes = (datetime.now(UTC) - claim_time).total_seconds() / 60

                est_duration = existing_claim.get("estimated_duration_minutes", 30)
                if elapsed_minutes < est_duration:
                    agent_name = existing_claim["agent_name"]
                    time_remaining = round(est_duration - elapsed_minutes, 1)
                    return {
                        "success": False,
                        "message": f"Target already claimed by {agent_name}",
                        "conflict": {
                            "claimed_by": agent_name,
                            "claimed_at": existing_claim["claimed_at"],
                            "test_type": existing_claim["test_type"],
                            "description": existing_claim.get("description"),
                            "time_remaining_minutes": time_remaining,
                        },
                        "suggestion": f"Try a different aspect or wait for {agent_name}",
                    }
                else:
                    # Claim expired, allow override
                    logger.info(f"Claim expired, allowing override: {claim_key}")

            # Create new claim
            claim_id = _generate_id("claim")
            claim_data = {
                "claim_id": claim_id,
                "target": target,
                "test_type": test_type,
                "description": description,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "claimed_at": _get_timestamp(),
                "estimated_duration_minutes": estimated_duration_minutes,
                "status": "active",
            }

            _claims[claim_key] = claim_data

        # Notify other agents about the claim
        _add_broadcast(
            agent_id=agent_id,
            agent_name=agent_name,
            message_type="claim",
            content=f"Claimed {target} for {test_type} testing",
            metadata={"claim_id": claim_id, "target": target, "test_type": test_type},
        )

        return {
            "success": True,
            "claim_id": claim_id,
            "message": f"Successfully claimed '{target}' for {test_type} testing",
            "claim_details": {
                "target": target,
                "test_type": test_type,
                "expires_in_minutes": estimated_duration_minutes,
            },
            "next_steps": [
                f"Perform {test_type} testing on {target}",
                "Use share_finding() if you discover vulnerabilities",
                "Use release_claim() when done or if you want to release early",
            ],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error claiming target: {e}")
        return {"success": False, "error": f"Failed to claim target: {e!s}"}


@register_tool(sandbox_execution=False)
def release_claim(
    agent_state: Any,
    claim_id: str | None = None,
    target: str | None = None,
    test_type: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Release a claim on a target, allowing other agents to test it.

    Call this when you've finished testing or want to let another agent handle it.

    Args:
        claim_id: The claim ID to release (from claim_target response)
        target: Alternative: specify target to release (use with test_type)
        test_type: Alternative: specify test type (use with target)
        reason: Optional reason for releasing
                (e.g., "completed", "blocked", "needs_different_approach")

    Returns:
        Dictionary containing:
        - success: Whether the release was successful
        - message: Status message
    """
    try:
        agent_id = agent_state.agent_id

        with _claims_lock:
            claim_to_release = None
            claim_key_to_remove = None

            if claim_id:
                # Find by claim_id
                for key, claim in _claims.items():
                    if claim["claim_id"] == claim_id:
                        if claim["agent_id"] == agent_id:
                            claim_to_release = claim
                            claim_key_to_remove = key
                        else:
                            return {
                                "success": False,
                                "error": "Cannot release another agent's claim",
                            }
                        break
            elif target and test_type:
                # Find by target and test_type
                claim_key = f"{target}:{test_type}".lower()
                if claim_key in _claims:
                    claim = _claims[claim_key]
                    if claim["agent_id"] == agent_id:
                        claim_to_release = claim
                        claim_key_to_remove = claim_key
                    else:
                        return {
                            "success": False,
                            "error": "Cannot release another agent's claim",
                        }
            else:
                return {
                    "success": False,
                    "error": "Must provide either claim_id or both target and test_type",
                }

            if claim_to_release and claim_key_to_remove:
                del _claims[claim_key_to_remove]

                # Broadcast the release
                _add_broadcast(
                    agent_id=agent_id,
                    agent_name=getattr(agent_state, "agent_name", "Unknown"),
                    message_type="release",
                    content=f"Released: {claim_to_release['target']} ({reason or 'done'})",
                    metadata={
                        "claim_id": claim_to_release["claim_id"],
                        "target": claim_to_release["target"],
                        "reason": reason,
                    },
                )

                return {
                    "success": True,
                    "message": f"Released claim on '{claim_to_release['target']}'",
                    "released_claim": {
                        "target": claim_to_release["target"],
                        "test_type": claim_to_release["test_type"],
                        "reason": reason,
                    },
                }
            else:
                return {"success": False, "error": "Claim not found"}

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error releasing claim: {e}")
        return {"success": False, "error": f"Failed to release claim: {e!s}"}


@register_tool(sandbox_execution=False)
def list_claims(
    agent_state: Any,
    filter_agent: str | None = None,
    filter_test_type: str | None = None,
    include_expired: bool = False,
) -> dict[str, Any]:
    """List all current claims to see what's being tested.

    Use this to find available targets or see what other agents are working on.

    Args:
        filter_agent: Filter by agent ID or name
        filter_test_type: Filter by test type (e.g., "sqli", "xss")
        include_expired: Include expired claims (default: False)

    Returns:
        Dictionary containing:
        - claims: List of active claims
        - total_count: Number of claims
        - by_agent: Claims grouped by agent
        - available_targets: Suggestions for unclaimed targets
    """
    try:
        current_agent_id = agent_state.agent_id
        now = datetime.now(UTC)

        with _claims_lock:
            active_claims = []
            expired_claims = []
            by_agent: dict[str, list[dict[str, Any]]] = {}

            for claim_key, claim in _claims.items():
                # Check expiration
                claim_time = datetime.fromisoformat(claim["claimed_at"].replace("Z", "+00:00"))
                elapsed_minutes = (now - claim_time).total_seconds() / 60
                is_expired = elapsed_minutes >= claim.get("estimated_duration_minutes", 30)

                # Apply filters
                if filter_agent:
                    agent_match = filter_agent.lower() in claim["agent_name"].lower()
                    id_match = filter_agent == claim["agent_id"]
                    if not agent_match and not id_match:
                        continue
                if filter_test_type:
                    if filter_test_type.lower() != claim["test_type"].lower():
                        continue

                claim_info = {
                    **claim,
                    "is_expired": is_expired,
                    "elapsed_minutes": round(elapsed_minutes, 1),
                    "is_mine": claim["agent_id"] == current_agent_id,
                }

                if is_expired:
                    expired_claims.append(claim_info)
                else:
                    active_claims.append(claim_info)

                # Group by agent
                agent_key = claim["agent_name"]
                if agent_key not in by_agent:
                    by_agent[agent_key] = []
                by_agent[agent_key].append(claim_info)

            result_claims = active_claims
            if include_expired:
                result_claims.extend(expired_claims)

        return {
            "success": True,
            "claims": result_claims,
            "total_count": len(result_claims),
            "active_count": len(active_claims),
            "expired_count": len(expired_claims),
            "by_agent": by_agent,
            "my_claims": [c for c in result_claims if c.get("is_mine")],
            "tips": [
                "Expired claims can be overridden by claiming the same target",
                "Use release_claim() when done to free up targets faster",
                "Check test_type to avoid testing the same vulnerability type",
            ],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error listing claims: {e}")
        return {"success": False, "error": f"Failed to list claims: {e!s}", "claims": []}


# =============================================================================
# FINDING SHARING
# Share discovered vulnerabilities so other agents can chain them
# =============================================================================


@register_tool(sandbox_execution=False)
def share_finding(
    agent_state: Any,
    title: str,
    finding_type: str,
    severity: Literal["critical", "high", "medium", "low", "info"],
    target: str,
    description: str,
    poc: str | None = None,
    chainable: bool = True,
    chain_suggestions: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Share a vulnerability finding with all agents for potential chaining.

    When you discover a vulnerability, share it so other agents can:
    - Avoid duplicating your discovery
    - Chain it with their findings for higher impact
    - Build upon your work

    Args:
        title: Brief title of the finding (e.g., "SSRF at /api/fetch")
        finding_type: Type of vulnerability (e.g., "ssrf", "sqli", "xss", "idor", "auth_bypass")
        severity: Severity level: "critical", "high", "medium", "low", "info"
        target: Where the vulnerability exists (URL, parameter, endpoint)
        description: Detailed description of the vulnerability
        poc: Proof-of-concept payload or steps to reproduce
        chainable: Whether this finding can be chained with others (default: True)
        chain_suggestions: Suggested ways to chain this vulnerability
                          Example: ["Chain IDOR", "Port scan internal"]
        tags: Additional tags for categorization (e.g., ["api", "file_upload", "admin"])

    Returns:
        Dictionary containing:
        - success: Whether sharing was successful
        - finding_id: Unique ID for the finding
        - broadcast_status: Whether other agents were notified
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        finding_id = _generate_id("finding")

        finding_data = {
            "finding_id": finding_id,
            "title": title,
            "finding_type": finding_type.lower(),
            "severity": severity.lower(),
            "target": target,
            "description": description,
            "poc": poc,
            "chainable": chainable,
            "chain_suggestions": chain_suggestions or [],
            "tags": tags or [],
            "discovered_by": {
                "agent_id": agent_id,
                "agent_name": agent_name,
            },
            "discovered_at": _get_timestamp(),
            "chained_with": [],  # Track if this gets chained with other findings
            "views": 0,
        }

        with _findings_lock:
            _shared_findings.append(finding_data)

        # Broadcast to all agents
        broadcast_content = f"🔴 NEW FINDING: [{severity.upper()}] {title}\n"
        broadcast_content += f"Type: {finding_type} | Target: {target}\n"
        if chainable and chain_suggestions:
            broadcast_content += f"Chain opportunities: {', '.join(chain_suggestions[:3])}"

        _add_broadcast(
            agent_id=agent_id,
            agent_name=agent_name,
            message_type="finding",
            content=broadcast_content,
            metadata={
                "finding_id": finding_id,
                "severity": severity,
                "finding_type": finding_type,
                "chainable": chainable,
            },
            priority="high" if severity in ["critical", "high"] else "normal",
        )

        return {
            "success": True,
            "finding_id": finding_id,
            "message": f"Shared finding: {title}",
            "broadcast_status": "All agents notified",
            "finding_summary": {
                "id": finding_id,
                "title": title,
                "severity": severity,
                "type": finding_type,
                "chainable": chainable,
            },
            "next_steps": [
                "Continue testing for additional vulnerabilities",
                "Check list_findings() to see if others found chainable vulns",
                "Consider creating a chain if you find related vulnerabilities",
            ],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error sharing finding: {e}")
        return {"success": False, "error": f"Failed to share finding: {e!s}"}


@register_tool(sandbox_execution=False)
def list_findings(
    agent_state: Any,
    filter_type: str | None = None,
    filter_severity: str | None = None,
    chainable_only: bool = False,
    exclude_own: bool = False,
    max_results: int = 50,
) -> dict[str, Any]:
    """List shared findings from all agents.

    Use this to:
    - See what vulnerabilities have been discovered
    - Find chainable vulnerabilities to combine with your findings
    - Avoid duplicate testing

    Args:
        filter_type: Filter by vulnerability type (e.g., "ssrf", "sqli")
        filter_severity: Filter by severity ("critical", "high", "medium", "low")
        chainable_only: Only show findings marked as chainable
        exclude_own: Exclude findings you discovered
        max_results: Maximum results to return (default: 50)

    Returns:
        Dictionary containing:
        - findings: List of shared findings
        - chain_opportunities: Suggested vulnerability chains
        - by_severity: Findings grouped by severity
    """
    try:
        current_agent_id = agent_state.agent_id

        with _findings_lock:
            filtered_findings = []

            for finding in _shared_findings:
                # Apply filters
                if filter_type and filter_type.lower() != finding["finding_type"]:
                    continue
                if filter_severity and filter_severity.lower() != finding["severity"]:
                    continue
                if chainable_only and not finding.get("chainable", False):
                    continue
                if exclude_own and finding["discovered_by"]["agent_id"] == current_agent_id:
                    continue

                filtered_findings.append(finding)

            # Sort by severity and recency
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            filtered_findings.sort(
                key=lambda x: (severity_order.get(x["severity"], 5), x["discovered_at"]),
                reverse=False,
            )

            filtered_findings = filtered_findings[:max_results]

        # Group by severity
        by_severity: dict[str, list[dict[str, Any]]] = {}
        for finding in filtered_findings:
            sev = finding["severity"]
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(finding)

        # Identify chain opportunities
        chain_opportunities = _identify_chain_opportunities(filtered_findings)

        return {
            "success": True,
            "findings": filtered_findings,
            "total_count": len(filtered_findings),
            "by_severity": by_severity,
            "severity_summary": {sev: len(findings) for sev, findings in by_severity.items()},
            "chain_opportunities": chain_opportunities,
            "tips": [
                "Use get_finding_details() for full PoC and description",
                "Chainable findings can be combined for higher impact",
                "Check chain_suggestions for recommended combinations",
            ],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error listing findings: {e}")
        return {"success": False, "error": f"Failed to list findings: {e!s}", "findings": []}


def _identify_chain_opportunities(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify potential vulnerability chains from findings."""
    chain_opportunities = []

    # Common chain patterns
    chain_patterns = [
        {
            "name": "SSRF to Internal Access",
            "types": ["ssrf"],
            "chains_with": ["idor", "auth_bypass", "info_disclosure"],
            "description": "Use SSRF to access internal services or bypass restrictions",
        },
        {
            "name": "XSS to Account Takeover",
            "types": ["xss", "stored_xss"],
            "chains_with": ["csrf", "session_hijack"],
            "description": "Chain XSS with session theft for account takeover",
        },
        {
            "name": "SQLi to Data Exfiltration",
            "types": ["sqli", "blind_sqli"],
            "chains_with": ["idor", "auth_bypass"],
            "description": "Use SQL injection to extract sensitive data",
        },
        {
            "name": "IDOR + Auth Bypass",
            "types": ["idor"],
            "chains_with": ["auth_bypass", "privilege_escalation"],
            "description": "Combine IDOR with auth issues for unauthorized access",
        },
        {
            "name": "File Upload to RCE",
            "types": ["file_upload", "unrestricted_upload"],
            "chains_with": ["lfi", "rce", "path_traversal"],
            "description": "Chain file upload with execution for RCE",
        },
    ]

    finding_types = {f["finding_type"] for f in findings if f.get("chainable")}

    for pattern in chain_patterns:
        # Check if we have findings matching the pattern
        has_primary = any(t in finding_types for t in pattern["types"])
        has_chain = any(t in finding_types for t in pattern["chains_with"])

        if has_primary or has_chain:
            relevant_findings = [
                f
                for f in findings
                if f["finding_type"] in pattern["types"]
                or f["finding_type"] in pattern["chains_with"]
            ]

            if relevant_findings:
                chain_opportunities.append(
                    {
                        "chain_name": pattern["name"],
                        "description": pattern["description"],
                        "relevant_findings": [
                            {"id": f["finding_id"], "title": f["title"], "type": f["finding_type"]}
                            for f in relevant_findings[:3]
                        ],
                        "potential_impact": "high" if has_primary and has_chain else "medium",
                    }
                )

    return chain_opportunities[:5]  # Top 5 chain opportunities


@register_tool(sandbox_execution=False)
def get_finding_details(agent_state: Any, finding_id: str) -> dict[str, Any]:
    """Get full details of a specific finding including PoC.

    Args:
        finding_id: The finding ID to retrieve

    Returns:
        Dictionary containing full finding details including PoC
    """
    try:
        with _findings_lock:
            for finding in _shared_findings:
                if finding["finding_id"] == finding_id:
                    # Increment view count
                    finding["views"] = finding.get("views", 0) + 1
                    return {
                        "success": True,
                        "finding": finding,
                        "chain_suggestions": finding.get("chain_suggestions", []),
                    }

        return {"success": False, "error": f"Finding {finding_id} not found"}

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error getting finding details: {e}")
        return {"success": False, "error": f"Failed to get finding details: {e!s}"}


# =============================================================================
# WORK QUEUE
# Central queue for coordinated testing
# =============================================================================


@register_tool(sandbox_execution=False)
def add_to_work_queue(
    agent_state: Any,
    target: str,
    test_types: list[str],
    priority: Literal["critical", "high", "medium", "low"] = "medium",
    description: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add an endpoint/parameter to the work queue for testing.

    Use this to add targets that need testing but you can't handle right now.
    Other agents can pick up items from the queue.

    Args:
        target: The target to test (URL, endpoint, parameter)
        test_types: List of test types needed (e.g., ["sqli", "xss", "idor"])
        priority: Priority level for testing
        description: Description or notes about the target
        context: Additional context (e.g., authentication requirements, headers)

    Returns:
        Dictionary containing:
        - success: Whether the item was added
        - queue_id: Unique ID for the queue item
        - queue_position: Position in the queue
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        queue_id = _generate_id("queue")

        queue_item = {
            "queue_id": queue_id,
            "target": target,
            "test_types": test_types,
            "priority": priority,
            "description": description,
            "context": context or {},
            "added_by": {
                "agent_id": agent_id,
                "agent_name": agent_name,
            },
            "added_at": _get_timestamp(),
            "status": "pending",
            "claimed_by": None,
        }

        with _queue_lock:
            _work_queue.append(queue_item)
            # Sort by priority
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            _work_queue.sort(key=lambda x: priority_order.get(x["priority"], 2))
            queue_position = _work_queue.index(queue_item) + 1

        return {
            "success": True,
            "queue_id": queue_id,
            "message": f"Added '{target}' to work queue",
            "queue_position": queue_position,
            "item_summary": {
                "target": target,
                "test_types": test_types,
                "priority": priority,
            },
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error adding to work queue: {e}")
        return {"success": False, "error": f"Failed to add to work queue: {e!s}"}


@register_tool(sandbox_execution=False)
def get_next_work_item(
    agent_state: Any,
    preferred_test_types: list[str] | None = None,
    auto_claim: bool = True,
) -> dict[str, Any]:
    """Get the next item from the work queue to test.

    Picks up an unclaimed item from the queue for testing.

    Args:
        preferred_test_types: Optional list of preferred test types to match
        auto_claim: Automatically claim the item (default: True)

    Returns:
        Dictionary containing:
        - success: Whether an item was found
        - work_item: The work item to test (if found)
        - claimed: Whether the item was auto-claimed
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        with _queue_lock:
            selected_item = None

            for item in _work_queue:
                if item["status"] != "pending":
                    continue

                # Check preferred test types
                if preferred_test_types:
                    if not any(t in item["test_types"] for t in preferred_test_types):
                        continue

                selected_item = item
                break

            if selected_item:
                if auto_claim:
                    selected_item["status"] = "claimed"
                    selected_item["claimed_by"] = {
                        "agent_id": agent_id,
                        "agent_name": agent_name,
                    }
                    selected_item["claimed_at"] = _get_timestamp()

                target = selected_item["target"]
                tests = ", ".join(selected_item["test_types"])
                return {
                    "success": True,
                    "work_item": selected_item,
                    "claimed": auto_claim,
                    "instructions": [
                        f"Test {target} for: {tests}",
                        "Use claim_target() if not auto-claimed",
                        "Use share_finding() when you discover vulnerabilities",
                    ],
                }

            return {
                "success": True,
                "work_item": None,
                "message": "No pending work items in queue",
                "suggestion": "Use add_to_work_queue() or check list_claims()",
            }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error getting work item: {e}")
        return {"success": False, "error": f"Failed to get work item: {e!s}"}


@register_tool(sandbox_execution=False)
def list_work_queue(
    agent_state: Any,
    status_filter: Literal["pending", "claimed", "completed", "all"] = "all",
    max_results: int = 50,
) -> dict[str, Any]:
    """List items in the work queue.

    Args:
        status_filter: Filter by status (default: "all")
        max_results: Maximum results to return

    Returns:
        Dictionary containing:
        - queue_items: List of work queue items
        - pending_count: Number of pending items
        - by_priority: Items grouped by priority
    """
    try:
        with _queue_lock:
            items = _work_queue.copy()

        if status_filter != "all":
            items = [i for i in items if i["status"] == status_filter]

        items = items[:max_results]

        # Group by priority
        by_priority: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            p = item["priority"]
            if p not in by_priority:
                by_priority[p] = []
            by_priority[p].append(item)

        pending_count = len([i for i in _work_queue if i["status"] == "pending"])

        return {
            "success": True,
            "queue_items": items,
            "total_count": len(items),
            "pending_count": pending_count,
            "by_priority": by_priority,
            "by_status": {
                "pending": len([i for i in items if i["status"] == "pending"]),
                "claimed": len([i for i in items if i["status"] == "claimed"]),
                "completed": len([i for i in items if i["status"] == "completed"]),
            },
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error listing work queue: {e}")
        return {"success": False, "error": f"Failed to list work queue: {e!s}", "queue_items": []}


# =============================================================================
# HELP REQUESTS
# Request specialized assistance from other agents
# =============================================================================


@register_tool(sandbox_execution=False)
def request_help(
    agent_state: Any,
    title: str,
    description: str,
    help_type: Literal["analysis", "exploitation", "bypass", "crypto", "reversing", "other"],
    target: str | None = None,
    urgency: Literal["low", "medium", "high", "critical"] = "medium",
    attachments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Request help from other agents for specialized tasks.

    Use this when you encounter something that needs specialized expertise
    that another agent might be able to help with.

    Args:
        title: Brief title of what you need help with
        description: Detailed description of the problem
        help_type: Type of help needed:
                   - "analysis": Need help analyzing something (encoded data, obfuscated code)
                   - "exploitation": Need help creating/refining an exploit
                   - "bypass": Need help bypassing a protection (WAF, filter, etc.)
                   - "crypto": Need help with cryptographic analysis
                   - "reversing": Need help with reverse engineering
                   - "other": Other specialized help
        target: The target/endpoint related to the request
        urgency: How urgent the request is
        attachments: Additional data (e.g., encoded strings, payloads tried)

    Returns:
        Dictionary containing:
        - success: Whether the request was created
        - request_id: Unique ID for the help request
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        request_id = _generate_id("help")

        help_request = {
            "request_id": request_id,
            "title": title,
            "description": description,
            "help_type": help_type,
            "target": target,
            "urgency": urgency,
            "attachments": attachments or {},
            "requested_by": {
                "agent_id": agent_id,
                "agent_name": agent_name,
            },
            "requested_at": _get_timestamp(),
            "status": "open",
            "responses": [],
        }

        with _help_lock:
            _help_requests.append(help_request)

        # Broadcast help request
        _add_broadcast(
            agent_id=agent_id,
            agent_name=agent_name,
            message_type="help_request",
            content=f"🆘 HELP NEEDED [{urgency.upper()}]: {title}\nType: {help_type}",
            metadata={"request_id": request_id, "help_type": help_type, "urgency": urgency},
            priority="high" if urgency in ["high", "critical"] else "normal",
        )

        return {
            "success": True,
            "request_id": request_id,
            "message": f"Help request created: {title}",
            "broadcast_status": "All agents notified",
            "next_steps": [
                "Continue with other tasks while waiting for help",
                "Check list_help_requests() to see responses",
                "Use respond_to_help_request() if you can help others",
            ],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error creating help request: {e}")
        return {"success": False, "error": f"Failed to create help request: {e!s}"}


@register_tool(sandbox_execution=False)
def respond_to_help_request(
    agent_state: Any,
    request_id: str,
    response: str,
    solution: str | None = None,
    can_take_over: bool = False,
) -> dict[str, Any]:
    """Respond to another agent's help request.

    Args:
        request_id: The help request ID to respond to
        response: Your response/suggestion
        solution: A specific solution if you have one
        can_take_over: Whether you're offering to take over this task

    Returns:
        Dictionary containing:
        - success: Whether the response was recorded
        - message: Status message
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        with _help_lock:
            for request in _help_requests:
                if request["request_id"] == request_id:
                    response_data = {
                        "response_id": _generate_id("resp"),
                        "responder": {
                            "agent_id": agent_id,
                            "agent_name": agent_name,
                        },
                        "response": response,
                        "solution": solution,
                        "can_take_over": can_take_over,
                        "responded_at": _get_timestamp(),
                    }

                    request["responses"].append(response_data)

                    # Notify the requester
                    _add_broadcast(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        message_type="help_response",
                        content=f"Response to help request: {request['title']}",
                        metadata={
                            "request_id": request_id,
                            "to_agent": request["requested_by"]["agent_id"],
                        },
                    )

                    return {
                        "success": True,
                        "message": "Response recorded and requester notified",
                        "request_title": request["title"],
                    }

        return {"success": False, "error": f"Help request {request_id} not found"}

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error responding to help request: {e}")
        return {"success": False, "error": f"Failed to respond to help request: {e!s}"}


@register_tool(sandbox_execution=False)
def list_help_requests(
    agent_state: Any,
    status_filter: Literal["open", "resolved", "all"] = "open",
    help_type_filter: str | None = None,
    include_own: bool = True,
) -> dict[str, Any]:
    """List help requests from all agents.

    Args:
        status_filter: Filter by status (default: "open")
        help_type_filter: Filter by help type
        include_own: Include your own requests (default: True)

    Returns:
        Dictionary containing:
        - requests: List of help requests
        - by_type: Requests grouped by help type
    """
    try:
        current_agent_id = agent_state.agent_id

        with _help_lock:
            requests = _help_requests.copy()

        # Apply filters
        if status_filter != "all":
            requests = [r for r in requests if r["status"] == status_filter]
        if help_type_filter:
            requests = [r for r in requests if r["help_type"] == help_type_filter]
        if not include_own:
            requests = [r for r in requests if r["requested_by"]["agent_id"] != current_agent_id]

        # Group by type
        by_type: dict[str, list[dict[str, Any]]] = {}
        for req in requests:
            t = req["help_type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(req)

        # Mark own requests
        for req in requests:
            req["is_mine"] = req["requested_by"]["agent_id"] == current_agent_id
            req["response_count"] = len(req.get("responses", []))

        return {
            "success": True,
            "requests": requests,
            "total_count": len(requests),
            "by_type": by_type,
            "my_requests": [r for r in requests if r.get("is_mine")],
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error listing help requests: {e}")
        return {"success": False, "error": f"Failed to list help requests: {e!s}", "requests": []}


# =============================================================================
# COLLABORATION STATUS
# Overview of all collaborative activities
# =============================================================================


@register_tool(sandbox_execution=False)
def get_collaboration_status(agent_state: Any) -> dict[str, Any]:
    """Get an overview of all collaboration activities.

    Returns a summary of:
    - Active claims
    - Shared findings
    - Work queue status
    - Help requests
    - Recent broadcasts

    Use this to get a quick snapshot of what all agents are doing.
    """
    try:
        current_agent_id = agent_state.agent_id
        now = datetime.now(UTC)

        with _claims_lock:
            active_claims = []
            my_claims = []
            for claim in _claims.values():
                claim_time = datetime.fromisoformat(claim["claimed_at"].replace("Z", "+00:00"))
                elapsed = (now - claim_time).total_seconds() / 60
                if elapsed < claim.get("estimated_duration_minutes", 30):
                    active_claims.append(claim)
                    if claim["agent_id"] == current_agent_id:
                        my_claims.append(claim)

        with _findings_lock:
            findings_count = len(_shared_findings)
            my_findings = [
                f for f in _shared_findings
                if f["discovered_by"]["agent_id"] == current_agent_id
            ]
            critical_findings = [
                f for f in _shared_findings if f["severity"] == "critical"
            ]
            chainable_findings = [f for f in _shared_findings if f.get("chainable")]

        with _queue_lock:
            pending_queue = [i for i in _work_queue if i["status"] == "pending"]
            claimed_by_me = [
                i for i in _work_queue
                if (i.get("claimed_by") or {}).get("agent_id") == current_agent_id
            ]

        with _help_lock:
            open_requests = [r for r in _help_requests if r["status"] == "open"]
            my_requests = [
                r for r in _help_requests
                if r["requested_by"]["agent_id"] == current_agent_id
            ]

        # Recent broadcasts
        recent_broadcasts = _broadcast_history[-10:] if _broadcast_history else []

        return {
            "success": True,
            "summary": {
                "active_claims": len(active_claims),
                "my_claims": len(my_claims),
                "total_findings": findings_count,
                "my_findings": len(my_findings),
                "critical_findings": len(critical_findings),
                "chainable_findings": len(chainable_findings),
                "pending_work_items": len(pending_queue),
                "my_work_items": len(claimed_by_me),
                "open_help_requests": len(open_requests),
                "my_help_requests": len(my_requests),
            },
            "my_activity": {
                "claims": my_claims,
                "findings": my_findings[-5:],  # Last 5 findings
                "work_items": claimed_by_me,
                "help_requests": my_requests,
            },
            "recent_broadcasts": recent_broadcasts,
            "chain_opportunities": _identify_chain_opportunities(_shared_findings),
            "recommendations": _generate_collaboration_recommendations(
                active_claims, _shared_findings, pending_queue, open_requests, current_agent_id
            ),
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error getting collaboration status: {e}")
        return {"success": False, "error": f"Failed to get collaboration status: {e!s}"}


def _generate_collaboration_recommendations(
    claims: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    help_requests: list[dict[str, Any]],
    agent_id: str,
) -> list[str]:
    """Generate recommendations for the agent based on current state."""
    recommendations = []

    # Check for unclaimed work
    if queue:
        recommendations.append(f"{len(queue)} items in queue - use get_next_work_item()")

    # Check for chainable findings
    chainable = [
        f for f in findings
        if f.get("chainable") and f["discovered_by"]["agent_id"] != agent_id
    ]
    if chainable:
        recommendations.append(f"{len(chainable)} chainable findings - check chain opportunities")

    # Check for unanswered help requests
    unanswered = [
        r for r in help_requests
        if not r.get("responses") and r["requested_by"]["agent_id"] != agent_id
    ]
    if unanswered:
        recommendations.append(f"{len(unanswered)} help requests need responses")

    # Check for critical findings
    critical = [f for f in findings if f["severity"] == "critical"]
    if critical:
        recommendations.append(f"{len(critical)} critical findings - prioritize exploitation")

    if not recommendations:
        recommendations.append("Collaboration is running smoothly - keep testing!")

    return recommendations


@register_tool(sandbox_execution=False)
def broadcast_message(
    agent_state: Any,
    message: str,
    message_type: Literal["info", "warning", "alert", "update"] = "info",
    priority: Literal["low", "normal", "high"] = "normal",
    target_agents: list[str] | None = None,
) -> dict[str, Any]:
    """Broadcast a message to all or specific agents.

    Use this for important updates that all agents should know about.

    Args:
        message: The message to broadcast
        message_type: Type of message (info, warning, alert, update)
        priority: Message priority
        target_agents: Optional list of specific agent IDs to message (default: all)

    Returns:
        Dictionary containing:
        - success: Whether the broadcast was successful
        - broadcast_id: Unique ID for the broadcast
    """
    try:
        agent_id = agent_state.agent_id
        agent_name = getattr(agent_state, "agent_name", "Unknown Agent")

        broadcast_id = _add_broadcast(
            agent_id=agent_id,
            agent_name=agent_name,
            message_type=message_type,
            content=message,
            metadata={"target_agents": target_agents},
            priority=priority,
        )

        return {
            "success": True,
            "broadcast_id": broadcast_id,
            "message": "Message broadcast successfully",
            "recipients": target_agents or "all agents",
        }

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error broadcasting message: {e}")
        return {"success": False, "error": f"Failed to broadcast message: {e!s}"}


def _add_broadcast(
    agent_id: str,
    agent_name: str,
    message_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    priority: str = "normal",
) -> str:
    """Add a broadcast message to the history."""
    broadcast_id = _generate_id("broadcast")

    broadcast = {
        "broadcast_id": broadcast_id,
        "from_agent": {
            "agent_id": agent_id,
            "agent_name": agent_name,
        },
        "message_type": message_type,
        "content": content,
        "metadata": metadata or {},
        "priority": priority,
        "timestamp": _get_timestamp(),
    }

    _broadcast_history.append(broadcast)

    # Keep only last 100 broadcasts
    while len(_broadcast_history) > 100:
        _broadcast_history.pop(0)

    return broadcast_id
