"""Tests for Multi-Agent Collaboration Protocol module."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

# Import the module under test
from strix.tools.collaboration.collaboration_actions import (
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
    _generate_id,
    _get_timestamp,
    _identify_chain_opportunities,
    # Clear state for testing
    _claims,
    _shared_findings,
    _work_queue,
    _help_requests,
    _broadcast_history,
)


@pytest.fixture
def mock_agent_state() -> MagicMock:
    """Create a mock agent state for testing."""
    state = MagicMock()
    state.agent_id = "agent_test123"
    state.agent_name = "Test Agent"
    return state


@pytest.fixture(autouse=True)
def clear_state() -> None:
    """Clear all shared state before each test."""
    _claims.clear()
    _shared_findings.clear()
    _work_queue.clear()
    _help_requests.clear()
    _broadcast_history.clear()


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_generate_id_with_prefix(self) -> None:
        """Test ID generation with prefix."""
        id1 = _generate_id("claim")
        id2 = _generate_id("claim")
        
        assert id1.startswith("claim_")
        assert id2.startswith("claim_")
        assert id1 != id2  # Should be unique

    def test_generate_id_without_prefix(self) -> None:
        """Test ID generation without prefix."""
        id1 = _generate_id()
        assert id1.startswith("_")

    def test_get_timestamp_format(self) -> None:
        """Test timestamp format."""
        ts = _get_timestamp()
        assert "T" in ts  # ISO format
        assert "+" in ts or "Z" in ts  # Timezone info


class TestClaimSystem:
    """Tests for the claim system."""

    def test_claim_target_success(self, mock_agent_state: MagicMock) -> None:
        """Test successful target claim."""
        result = claim_target(
            mock_agent_state,
            target="/api/users",
            test_type="sqli",
            description="Testing SQL injection",
            estimated_duration_minutes=30,
        )

        assert result["success"] is True
        assert "claim_id" in result
        assert result["claim_details"]["target"] == "/api/users"
        assert result["claim_details"]["test_type"] == "sqli"

    def test_claim_target_conflict(self, mock_agent_state: MagicMock) -> None:
        """Test claim conflict when target already claimed."""
        # First claim
        claim_target(mock_agent_state, "/api/users", "sqli")

        # Second claim with different agent
        other_agent = MagicMock()
        other_agent.agent_id = "agent_other456"
        other_agent.agent_name = "Other Agent"

        result = claim_target(other_agent, "/api/users", "sqli")

        assert result["success"] is False
        assert "conflict" in result
        assert result["conflict"]["claimed_by"] == "Test Agent"

    def test_claim_target_different_test_type(self, mock_agent_state: MagicMock) -> None:
        """Test claiming same target with different test type."""
        claim_target(mock_agent_state, "/api/users", "sqli")
        
        other_agent = MagicMock()
        other_agent.agent_id = "agent_other456"
        other_agent.agent_name = "Other Agent"
        
        result = claim_target(other_agent, "/api/users", "xss")
        
        # Different test type should succeed
        assert result["success"] is True

    def test_release_claim_by_id(self, mock_agent_state: MagicMock) -> None:
        """Test releasing claim by claim ID."""
        claim_result = claim_target(mock_agent_state, "/api/users", "sqli")
        claim_id = claim_result["claim_id"]

        result = release_claim(mock_agent_state, claim_id=claim_id, reason="completed")

        assert result["success"] is True
        assert result["released_claim"]["target"] == "/api/users"
        assert result["released_claim"]["reason"] == "completed"

    def test_release_claim_by_target(self, mock_agent_state: MagicMock) -> None:
        """Test releasing claim by target and test type."""
        claim_target(mock_agent_state, "/api/users", "sqli")

        result = release_claim(
            mock_agent_state,
            target="/api/users",
            test_type="sqli",
        )

        assert result["success"] is True

    def test_release_claim_other_agent(self, mock_agent_state: MagicMock) -> None:
        """Test that agents cannot release other agents' claims."""
        claim_result = claim_target(mock_agent_state, "/api/users", "sqli")

        other_agent = MagicMock()
        other_agent.agent_id = "agent_other456"

        result = release_claim(other_agent, claim_id=claim_result["claim_id"])

        assert result["success"] is False
        assert "Cannot release another agent's claim" in result["error"]

    def test_list_claims_empty(self, mock_agent_state: MagicMock) -> None:
        """Test listing claims when empty."""
        result = list_claims(mock_agent_state)

        assert result["success"] is True
        assert result["claims"] == []
        assert result["total_count"] == 0

    def test_list_claims_with_data(self, mock_agent_state: MagicMock) -> None:
        """Test listing claims with data."""
        claim_target(mock_agent_state, "/api/users", "sqli")
        claim_target(mock_agent_state, "/api/items", "xss")

        result = list_claims(mock_agent_state)

        assert result["success"] is True
        assert result["total_count"] == 2
        assert len(result["my_claims"]) == 2

    def test_list_claims_filter_by_test_type(self, mock_agent_state: MagicMock) -> None:
        """Test filtering claims by test type."""
        claim_target(mock_agent_state, "/api/users", "sqli")
        claim_target(mock_agent_state, "/api/items", "xss")

        result = list_claims(mock_agent_state, filter_test_type="sqli")

        assert result["success"] is True
        assert result["total_count"] == 1


class TestFindingSharing:
    """Tests for the finding sharing system."""

    def test_share_finding_success(self, mock_agent_state: MagicMock) -> None:
        """Test successful finding sharing."""
        result = share_finding(
            mock_agent_state,
            title="SSRF at /api/fetch",
            finding_type="ssrf",
            severity="high",
            target="/api/fetch?url=",
            description="URL parameter allows internal requests",
            poc="GET /api/fetch?url=http://169.254.169.254/",
            chainable=True,
            chain_suggestions=["Access internal services", "Cloud metadata"],
        )

        assert result["success"] is True
        assert "finding_id" in result
        assert result["finding_summary"]["severity"] == "high"
        assert result["finding_summary"]["chainable"] is True

    def test_list_findings_empty(self, mock_agent_state: MagicMock) -> None:
        """Test listing findings when empty."""
        result = list_findings(mock_agent_state)

        assert result["success"] is True
        assert result["findings"] == []
        assert result["total_count"] == 0

    def test_list_findings_with_data(self, mock_agent_state: MagicMock) -> None:
        """Test listing findings with data."""
        share_finding(
            mock_agent_state,
            title="SSRF",
            finding_type="ssrf",
            severity="high",
            target="/api/fetch",
            description="Test",
        )
        share_finding(
            mock_agent_state,
            title="SQLi",
            finding_type="sqli",
            severity="critical",
            target="/api/users",
            description="Test",
        )

        result = list_findings(mock_agent_state)

        assert result["success"] is True
        assert result["total_count"] == 2

    def test_list_findings_filter_severity(self, mock_agent_state: MagicMock) -> None:
        """Test filtering findings by severity."""
        share_finding(
            mock_agent_state, "Low", "xss", "low", "/test", "Test"
        )
        share_finding(
            mock_agent_state, "Critical", "sqli", "critical", "/test", "Test"
        )

        result = list_findings(mock_agent_state, filter_severity="critical")

        assert result["success"] is True
        assert result["total_count"] == 1
        assert result["findings"][0]["severity"] == "critical"

    def test_list_findings_chainable_only(self, mock_agent_state: MagicMock) -> None:
        """Test filtering for chainable findings only."""
        share_finding(
            mock_agent_state, "Chainable", "ssrf", "high", "/test", "Test",
            chainable=True
        )
        share_finding(
            mock_agent_state, "Not Chainable", "info", "low", "/test", "Test",
            chainable=False
        )

        result = list_findings(mock_agent_state, chainable_only=True)

        assert result["success"] is True
        assert result["total_count"] == 1
        assert result["findings"][0]["chainable"] is True

    def test_get_finding_details(self, mock_agent_state: MagicMock) -> None:
        """Test getting finding details."""
        share_result = share_finding(
            mock_agent_state,
            title="SSRF Test",
            finding_type="ssrf",
            severity="high",
            target="/api/fetch",
            description="Detailed description",
            poc="GET /api/fetch?url=http://internal/",
        )
        finding_id = share_result["finding_id"]

        result = get_finding_details(mock_agent_state, finding_id)

        assert result["success"] is True
        assert result["finding"]["title"] == "SSRF Test"
        assert result["finding"]["poc"] == "GET /api/fetch?url=http://internal/"

    def test_get_finding_details_not_found(self, mock_agent_state: MagicMock) -> None:
        """Test getting details for non-existent finding."""
        result = get_finding_details(mock_agent_state, "nonexistent_id")

        assert result["success"] is False
        assert "not found" in result["error"]


class TestChainOpportunities:
    """Tests for vulnerability chain identification."""

    def test_identify_ssrf_chain(self) -> None:
        """Test identifying SSRF chain opportunities."""
        findings = [
            {"finding_id": "1", "finding_type": "ssrf", "title": "SSRF", "chainable": True},
            {"finding_id": "2", "finding_type": "idor", "title": "IDOR", "chainable": True},
        ]

        chains = _identify_chain_opportunities(findings)

        assert len(chains) > 0
        chain_names = [c["chain_name"] for c in chains]
        assert "SSRF to Internal Access" in chain_names

    def test_identify_xss_chain(self) -> None:
        """Test identifying XSS chain opportunities."""
        findings = [
            {"finding_id": "1", "finding_type": "xss", "title": "XSS", "chainable": True},
            {"finding_id": "2", "finding_type": "csrf", "title": "CSRF", "chainable": True},
        ]

        chains = _identify_chain_opportunities(findings)

        assert len(chains) > 0


class TestWorkQueue:
    """Tests for the work queue system."""

    def test_add_to_queue_success(self, mock_agent_state: MagicMock) -> None:
        """Test adding item to work queue."""
        result = add_to_work_queue(
            mock_agent_state,
            target="/admin/users",
            test_types=["sqli", "idor"],
            priority="high",
            description="Admin endpoint",
        )

        assert result["success"] is True
        assert "queue_id" in result
        assert result["queue_position"] >= 1

    def test_add_to_queue_priority_sorting(self, mock_agent_state: MagicMock) -> None:
        """Test that queue is sorted by priority."""
        add_to_work_queue(mock_agent_state, "/low", ["test"], priority="low")
        add_to_work_queue(mock_agent_state, "/critical", ["test"], priority="critical")
        add_to_work_queue(mock_agent_state, "/medium", ["test"], priority="medium")

        result = list_work_queue(mock_agent_state)

        # Critical should be first
        assert result["queue_items"][0]["priority"] == "critical"

    def test_get_next_work_item(self, mock_agent_state: MagicMock) -> None:
        """Test getting next work item from queue."""
        add_to_work_queue(mock_agent_state, "/test", ["sqli"])

        result = get_next_work_item(mock_agent_state)

        assert result["success"] is True
        assert result["work_item"] is not None
        assert result["claimed"] is True
        assert result["work_item"]["target"] == "/test"

    def test_get_next_work_item_empty(self, mock_agent_state: MagicMock) -> None:
        """Test getting next item from empty queue."""
        result = get_next_work_item(mock_agent_state)

        assert result["success"] is True
        assert result["work_item"] is None

    def test_get_next_work_item_preferred_types(self, mock_agent_state: MagicMock) -> None:
        """Test getting work item with preferred test types."""
        add_to_work_queue(mock_agent_state, "/xss", ["xss"])
        add_to_work_queue(mock_agent_state, "/sqli", ["sqli"])

        result = get_next_work_item(
            mock_agent_state,
            preferred_test_types=["sqli"],
        )

        assert result["success"] is True
        assert result["work_item"]["target"] == "/sqli"

    def test_list_work_queue(self, mock_agent_state: MagicMock) -> None:
        """Test listing work queue."""
        add_to_work_queue(mock_agent_state, "/test1", ["sqli"])
        add_to_work_queue(mock_agent_state, "/test2", ["xss"])

        result = list_work_queue(mock_agent_state)

        assert result["success"] is True
        assert result["total_count"] == 2
        assert result["pending_count"] == 2


class TestHelpRequests:
    """Tests for the help request system."""

    def test_request_help_success(self, mock_agent_state: MagicMock) -> None:
        """Test creating a help request."""
        result = request_help(
            mock_agent_state,
            title="Need help with encoded parameter",
            description="Found base64 encoded data",
            help_type="analysis",
            target="/api/session",
            urgency="medium",
        )

        assert result["success"] is True
        assert "request_id" in result
        assert result["broadcast_status"] == "All agents notified"

    def test_respond_to_help_request(self, mock_agent_state: MagicMock) -> None:
        """Test responding to a help request."""
        # Create help request
        help_result = request_help(
            mock_agent_state,
            title="Test help",
            description="Test",
            help_type="analysis",
        )
        request_id = help_result["request_id"]

        # Respond to it
        other_agent = MagicMock()
        other_agent.agent_id = "agent_helper"
        other_agent.agent_name = "Helper Agent"

        result = respond_to_help_request(
            other_agent,
            request_id=request_id,
            response="Here's how to decode it...",
            solution="Use base64 -d",
        )

        assert result["success"] is True

    def test_list_help_requests(self, mock_agent_state: MagicMock) -> None:
        """Test listing help requests."""
        request_help(
            mock_agent_state,
            title="Help 1",
            description="Test",
            help_type="analysis",
        )
        request_help(
            mock_agent_state,
            title="Help 2",
            description="Test",
            help_type="exploitation",
        )

        result = list_help_requests(mock_agent_state)

        assert result["success"] is True
        assert result["total_count"] == 2

    def test_list_help_requests_filter_type(self, mock_agent_state: MagicMock) -> None:
        """Test filtering help requests by type."""
        request_help(mock_agent_state, "Analysis", "Test", "analysis")
        request_help(mock_agent_state, "Exploitation", "Test", "exploitation")

        result = list_help_requests(
            mock_agent_state,
            help_type_filter="analysis",
        )

        assert result["success"] is True
        assert result["total_count"] == 1


class TestCollaborationStatus:
    """Tests for collaboration status overview."""

    def test_get_status_empty(self, mock_agent_state: MagicMock) -> None:
        """Test getting status with no activity."""
        result = get_collaboration_status(mock_agent_state)

        assert result["success"] is True
        assert result["summary"]["active_claims"] == 0
        assert result["summary"]["total_findings"] == 0
        assert result["summary"]["pending_work_items"] == 0

    def test_get_status_with_activity(self, mock_agent_state: MagicMock) -> None:
        """Test getting status with activity."""
        claim_target(mock_agent_state, "/test", "sqli")
        share_finding(
            mock_agent_state, "Test", "ssrf", "high", "/test", "Test"
        )
        add_to_work_queue(mock_agent_state, "/work", ["test"])

        result = get_collaboration_status(mock_agent_state)

        assert result["success"] is True
        assert result["summary"]["active_claims"] >= 1
        assert result["summary"]["total_findings"] >= 1
        assert result["summary"]["pending_work_items"] >= 1


class TestBroadcastMessage:
    """Tests for message broadcasting."""

    def test_broadcast_message_success(self, mock_agent_state: MagicMock) -> None:
        """Test successful message broadcast."""
        result = broadcast_message(
            mock_agent_state,
            message="WAF detected, use tamper scripts",
            message_type="warning",
            priority="high",
        )

        assert result["success"] is True
        assert "broadcast_id" in result

    def test_broadcast_message_to_specific_agents(self, mock_agent_state: MagicMock) -> None:
        """Test broadcasting to specific agents."""
        result = broadcast_message(
            mock_agent_state,
            message="Direct message",
            target_agents=["agent_123", "agent_456"],
        )

        assert result["success"] is True
        assert result["recipients"] == ["agent_123", "agent_456"]
