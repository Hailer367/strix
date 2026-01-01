"""
Comprehensive tests for StrixDB Target Tracking System.

Tests all target tracking functionality including:
- Target initialization
- Session management
- Finding recording
- Endpoint tracking
- Note management
- Progress tracking
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# Mock agent state for tests
@pytest.fixture
def mock_agent_state():
    return MagicMock()


@pytest.fixture
def mock_strixdb_config():
    """Mock StrixDB configuration."""
    return {
        "repo": "testuser/StrixDB",
        "token": "test_token",
        "branch": "main",
        "api_base": "https://api.github.com",
    }


class TestTargetSlugGeneration:
    """Tests for target slug generation."""
    
    def test_sanitize_url_target(self):
        """Test sanitizing URL targets."""
        from strix.tools.strixdb.strixdb_targets import _sanitize_target_slug
        
        # Test HTTPS URL
        assert _sanitize_target_slug("https://example.com") == "example.com"
        
        # Test with path
        assert _sanitize_target_slug("https://api.example.com/v1/users") == "api.example.com"
        
        # Test with port
        assert _sanitize_target_slug("https://example.com:8080") == "example.com"
    
    def test_sanitize_ip_target(self):
        """Test sanitizing IP targets."""
        from strix.tools.strixdb.strixdb_targets import _sanitize_target_slug
        
        # Test IP address
        result = _sanitize_target_slug("192.168.1.1")
        assert "192" in result
        assert "_" in result or "." in result
    
    def test_sanitize_domain_target(self):
        """Test sanitizing domain targets."""
        from strix.tools.strixdb.strixdb_targets import _sanitize_target_slug
        
        # Test simple domain
        assert _sanitize_target_slug("example.com") == "example.com"
        
        # Test subdomain
        result = _sanitize_target_slug("api.staging.example.com")
        assert "api" in result or "example" in result


class TestTargetProfileCreation:
    """Tests for target profile creation."""
    
    def test_create_initial_profile(self):
        """Test creating initial target profile."""
        from strix.tools.strixdb.strixdb_targets import _create_initial_target_profile
        
        profile = _create_initial_target_profile(
            target="https://example.com",
            target_type="web_app",
            description="Test target",
            scope=["example.com"],
            tags=["test"],
        )
        
        assert profile["target"] == "https://example.com"
        assert profile["target_type"] == "web_app"
        assert profile["description"] == "Test target"
        assert profile["status"] == "initialized"
        assert profile["total_sessions"] == 0
        assert "id" in profile
        assert "created_at" in profile
        assert "stats" in profile
        assert "tested_areas" in profile
        assert "pending_work" in profile
    
    def test_profile_stats_structure(self):
        """Test profile stats structure."""
        from strix.tools.strixdb.strixdb_targets import _create_initial_target_profile
        
        profile = _create_initial_target_profile(
            target="https://example.com",
            target_type="api",
        )
        
        stats = profile["stats"]
        assert stats["total_findings"] == 0
        assert stats["critical"] == 0
        assert stats["high"] == 0
        assert stats["medium"] == 0
        assert stats["low"] == 0
        assert stats["info"] == 0
        assert stats["endpoints_discovered"] == 0
    
    def test_profile_tested_areas_structure(self):
        """Test tested areas structure."""
        from strix.tools.strixdb.strixdb_targets import _create_initial_target_profile
        
        profile = _create_initial_target_profile(
            target="https://example.com",
            target_type="web_app",
        )
        
        tested = profile["tested_areas"]
        assert "reconnaissance" in tested
        assert "vulnerability_types" in tested
        assert "endpoints_tested" in tested


class TestSessionDataCreation:
    """Tests for session data creation."""
    
    def test_create_session_data(self):
        """Test creating session data structure."""
        from strix.tools.strixdb.strixdb_targets import _create_session_data
        
        session = _create_session_data(
            session_id="session_test_123",
            target_slug="example.com",
            objective="Test authentication",
            focus_areas=["auth", "jwt"],
        )
        
        assert session["session_id"] == "session_test_123"
        assert session["target_slug"] == "example.com"
        assert session["objective"] == "Test authentication"
        assert session["focus_areas"] == ["auth", "jwt"]
        assert session["status"] == "active"
        assert "started_at" in session
        assert session["ended_at"] is None
    
    def test_session_endpoints_structure(self):
        """Test session endpoints structure."""
        from strix.tools.strixdb.strixdb_targets import _create_session_data
        
        session = _create_session_data(
            session_id="session_test",
            target_slug="test",
        )
        
        endpoints = session["endpoints"]
        assert "discovered" in endpoints
        assert "tested" in endpoints
        assert "vulnerable" in endpoints
    
    def test_session_continuation_notes_structure(self):
        """Test continuation notes structure."""
        from strix.tools.strixdb.strixdb_targets import _create_session_data
        
        session = _create_session_data(
            session_id="session_test",
            target_slug="test",
        )
        
        notes = session["continuation_notes"]
        assert "immediate_follow_ups" in notes
        assert "promising_leads" in notes
        assert "blocked_by" in notes
        assert "recommendations" in notes


class TestTargetInit:
    """Tests for strixdb_target_init function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    def test_init_without_config(self, mock_config, mock_agent_state):
        """Test init fails gracefully without config."""
        mock_config.return_value = {"repo": "", "token": ""}
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_init
        
        result = strixdb_target_init(
            mock_agent_state,
            target="https://example.com",
        )
        
        assert result["success"] is False
        assert "not configured" in result["error"].lower()
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._ensure_target_directory')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_init_new_target(
        self,
        mock_save,
        mock_ensure_dir,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test initializing a new target."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({}, None)  # No existing profile
        mock_ensure_dir.return_value = True
        mock_save.return_value = True
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_init
        
        result = strixdb_target_init(
            mock_agent_state,
            target="https://example.com",
            target_type="web_app",
            description="Test target",
        )
        
        assert result["success"] is True
        assert result["is_new"] is True
        assert "target" in result
        assert mock_save.called
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    def test_init_existing_target(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test init returns existing target data."""
        mock_config.return_value = mock_strixdb_config
        
        existing_profile = {
            "slug": "example.com",
            "total_sessions": 5,
            "stats": {"total_findings": 10},
            "tested_areas": {"vulnerability_types": ["xss"]},
            "pending_work": {"high_priority": ["test auth"]},
            "quick_info": {},
        }
        mock_get_file.return_value = (existing_profile, "existing_sha")
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_init
        
        result = strixdb_target_init(
            mock_agent_state,
            target="https://example.com",
        )
        
        assert result["success"] is True
        assert result["is_new"] is False
        assert result["target"]["previous_sessions_count"] == 5


class TestTargetSessionStart:
    """Tests for strixdb_target_session_start function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_session_start_success(
        self,
        mock_save,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test starting a session successfully."""
        mock_config.return_value = mock_strixdb_config
        mock_save.return_value = True
        
        # Mock different files
        def get_file_side_effect(config, slug, filename, default):
            if filename == "profile.json":
                return ({"total_sessions": 2, "stats": {}, "tested_areas": {}, "pending_work": {}, "quick_info": {}}, "sha1")
            elif filename == "endpoints.json":
                return ({"discovered": ["/api/v1"], "tested": [], "vulnerable": []}, "sha2")
            elif filename == "technologies.json":
                return ({"identified": ["nginx"], "versions": {}}, "sha3")
            elif filename == "findings.json":
                return ({"vulnerabilities": [], "informational": []}, "sha4")
            elif filename == "notes.json":
                return ({"entries": []}, "sha5")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_session_start
        
        result = strixdb_target_session_start(
            mock_agent_state,
            target="https://example.com",
            objective="Test authentication",
            focus_areas=["auth", "jwt"],
        )
        
        assert result["success"] is True
        assert "session" in result
        assert "session_id" in result["session"]
        assert "target_summary" in result
        assert "continuation_guidance" in result


class TestTargetAddFinding:
    """Tests for strixdb_target_add_finding function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_add_critical_finding(
        self,
        mock_save,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test adding a critical finding."""
        mock_config.return_value = mock_strixdb_config
        mock_save.return_value = True
        
        def get_file_side_effect(config, slug, filename, default):
            if filename == "findings.json":
                return ({"vulnerabilities": [], "informational": []}, "sha1")
            elif filename == "profile.json":
                return ({"stats": {"total_findings": 0, "critical": 0}, "quick_info": {}, "tested_areas": {}}, "sha2")
            elif "session_" in filename:
                return ({"findings": [], "metrics": {"findings_count": 0}}, "sha3")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_add_finding
        
        result = strixdb_target_add_finding(
            mock_agent_state,
            target="https://example.com",
            session_id="session_test_123",
            title="SQL Injection in Login",
            severity="critical",
            vulnerability_type="sqli",
            description="Found SQL injection vulnerability...",
            affected_endpoint="/api/login",
            proof_of_concept="' OR '1'='1'--",
        )
        
        assert result["success"] is True
        assert "finding" in result
        assert result["finding"]["severity"] == "critical"
        assert result["finding"]["vulnerability_type"] == "sqli"


class TestTargetAddEndpoint:
    """Tests for strixdb_target_add_endpoint function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_add_new_endpoint(
        self,
        mock_save,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test adding a new endpoint."""
        mock_config.return_value = mock_strixdb_config
        mock_save.return_value = True
        
        def get_file_side_effect(config, slug, filename, default):
            if filename == "endpoints.json":
                return ({"discovered": [], "tested": [], "vulnerable": []}, "sha1")
            elif filename == "profile.json":
                return ({"stats": {"endpoints_discovered": 0}, "quick_info": {}}, "sha2")
            elif "session_" in filename:
                return ({"endpoints": {"discovered": [], "tested": []}, "metrics": {"endpoints_discovered": 0}}, "sha3")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_add_endpoint
        
        result = strixdb_target_add_endpoint(
            mock_agent_state,
            target="https://example.com",
            session_id="session_test_123",
            endpoint="/api/v1/users",
            method="POST",
            parameters=["username", "password"],
            auth_required=True,
        )
        
        assert result["success"] is True
        assert result["is_new"] is True
        assert result["endpoint"]["endpoint"] == "/api/v1/users"


class TestTargetUpdateProgress:
    """Tests for strixdb_target_update_progress function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_update_progress(
        self,
        mock_save,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test updating progress tracking."""
        mock_config.return_value = mock_strixdb_config
        mock_save.return_value = True
        
        def get_file_side_effect(config, slug, filename, default):
            if filename == "profile.json":
                return ({
                    "tested_areas": {"reconnaissance": [], "vulnerability_types": [], "endpoints_tested": []},
                    "pending_work": {"high_priority": [], "medium_priority": []},
                    "updated_at": ""
                }, "sha1")
            elif "session_" in filename:
                return ({"metrics": {"tools_used": []}}, "sha2")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_update_progress
        
        result = strixdb_target_update_progress(
            mock_agent_state,
            target="https://example.com",
            session_id="session_test_123",
            recon_completed=["subdomain_enum", "port_scan"],
            vuln_types_tested=["sqli", "xss"],
            tools_used=["nmap", "sqlmap"],
        )
        
        assert result["success"] is True
        assert "tested_areas" in result
        assert "subdomain_enum" in result["tested_areas"]["reconnaissance"]
        assert "sqli" in result["tested_areas"]["vulnerability_types"]


class TestTargetList:
    """Tests for strixdb_target_list function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('requests.get')
    def test_list_targets(
        self,
        mock_requests_get,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test listing all targets."""
        mock_config.return_value = mock_strixdb_config
        
        # Mock directory listing
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "dir", "name": "example.com"},
            {"type": "dir", "name": "api.test.com"},
        ]
        mock_requests_get.return_value = mock_response
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_list
        
        with patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file') as mock_get:
            mock_get.return_value = ({
                "target": "example.com",
                "target_type": "web_app",
                "status": "active",
                "total_sessions": 3,
                "last_scan_at": "2024-01-01T00:00:00Z",
                "stats": {"total_findings": 5},
            }, "sha")
            
            result = strixdb_target_list(mock_agent_state, include_stats=True)
        
        assert result["success"] is True
        assert len(result["targets"]) == 2


class TestTargetSessionEnd:
    """Tests for strixdb_target_session_end function."""
    
    @patch('strix.tools.strixdb.strixdb_targets._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_targets._get_or_create_target_file')
    @patch('strix.tools.strixdb.strixdb_targets._save_target_file')
    def test_session_end_success(
        self,
        mock_save,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test ending a session successfully."""
        mock_config.return_value = mock_strixdb_config
        mock_save.return_value = True
        
        def get_file_side_effect(config, slug, filename, default):
            if "session_" in filename:
                return ({
                    "started_at": "2024-01-01T10:00:00+00:00",
                    "metrics": {"findings_count": 2},
                }, "sha1")
            elif filename == "profile.json":
                return ({
                    "status": "active",
                    "pending_work": {"high_priority": [], "medium_priority": [], "follow_ups": []},
                    "session_history": [],
                    "quick_info": {},
                }, "sha2")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_targets import strixdb_target_session_end
        
        result = strixdb_target_session_end(
            mock_agent_state,
            target="https://example.com",
            session_id="session_test_123",
            summary="Completed authentication testing",
            accomplishments=["Found JWT bypass", "Mapped all endpoints"],
            immediate_follow_ups=["Exploit JWT for admin access"],
            promising_leads=["GraphQL endpoint found"],
        )
        
        assert result["success"] is True
        assert "session_summary" in result
        assert "continuation_saved" in result
