"""Multi-Agent Collaboration Protocol for Strix.

This module provides tools for efficient collaboration between AI agents:
- Claim System: Prevent duplicate work by claiming endpoints/parameters
- Finding Sharing: Share discovered vulnerabilities for chaining opportunities
- Work Queue: Central queue for coordinated testing
- Help Requests: Request specialized assistance from other agents

Enables more efficient testing, better vulnerability chaining, and no missed opportunities.
"""

from .collaboration_actions import (
    claim_target,
    release_claim,
    list_claims,
    share_finding,
    list_findings,
    get_finding_details,
    add_to_work_queue,
    get_next_work_item,
    list_work_queue,
    request_help,
    respond_to_help_request,
    list_help_requests,
    get_collaboration_status,
    broadcast_message,
)


__all__ = [
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
