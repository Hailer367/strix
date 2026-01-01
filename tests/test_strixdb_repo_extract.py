"""
Comprehensive tests for StrixDB Repository Knowledge Extraction System.

Tests all repository extraction functionality including:
- Repository initialization and cloning
- File extraction (single and batch)
- Category extraction
- Search and retrieval
- Status tracking
"""

import json
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, mock_open

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


class TestRepoSlugGeneration:
    """Tests for repository slug generation."""
    
    def test_sanitize_https_url(self):
        """Test sanitizing HTTPS repository URL."""
        from strix.tools.strixdb.strixdb_repo_extract import _sanitize_repo_slug
        
        # Test standard HTTPS URL
        assert _sanitize_repo_slug("https://github.com/owner/repo") == "owner_repo"
        
        # Test with .git suffix
        assert _sanitize_repo_slug("https://github.com/owner/repo.git") == "owner_repo"
    
    def test_sanitize_ssh_url(self):
        """Test sanitizing SSH repository URL."""
        from strix.tools.strixdb.strixdb_repo_extract import _sanitize_repo_slug
        
        # Test SSH URL
        result = _sanitize_repo_slug("git@github.com:owner/repo.git")
        assert "owner" in result or "repo" in result
    
    def test_sanitize_complex_names(self):
        """Test sanitizing repos with complex names."""
        from strix.tools.strixdb.strixdb_repo_extract import _sanitize_repo_slug
        
        # Test with hyphens
        result = _sanitize_repo_slug("https://github.com/awesome-owner/awesome-repo")
        assert "awesome" in result.lower()
        
        # Test multiple underscores collapse
        result = _sanitize_repo_slug("https://github.com/owner---test/repo___test")
        assert "___" not in result


class TestFileCategorization:
    """Tests for file categorization logic."""
    
    def test_categorize_python_script(self):
        """Test categorizing Python files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        # Note: path patterns take priority over extension
        # Patterns are checked in order, some paths may match multiple patterns
        # "exploit" pattern comes before "tool" pattern, so exploit wins
        assert _categorize_file("automation/mycode.py") == "scripts"  # No pattern match, uses extension
        assert _categorize_file("tools/exploit.py") == "exploits"  # "exploit" pattern wins over "tools"
        assert _categorize_file("utils/helper.py") == "tools"  # "util" pattern -> tools
    
    def test_categorize_shell_script(self):
        """Test categorizing shell scripts."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("install.sh") == "scripts"
        assert _categorize_file("setup.bash") == "scripts"
    
    def test_categorize_documentation(self):
        """Test categorizing documentation files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("README.md") == "documentation"
        assert _categorize_file("docs/guide.md") == "documentation"
    
    def test_categorize_wordlists(self):
        """Test categorizing wordlist files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("common.txt") == "wordlists"
        assert _categorize_file("wordlists/passwords.txt") == "wordlists"
    
    def test_categorize_payloads(self):
        """Test categorizing payload files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("payloads/xss.txt") == "payloads"
        assert _categorize_file("sqli/injection.txt") == "payloads"
    
    def test_categorize_exploits(self):
        """Test categorizing exploit files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("exploits/cve-2024-1234.py") == "exploits"
        assert _categorize_file("poc/exploit.sh") == "exploits"
    
    def test_categorize_configs(self):
        """Test categorizing configuration files."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        assert _categorize_file("config.yaml") == "configs"
        assert _categorize_file("settings.json") == "configs"
        assert _categorize_file("app.toml") == "configs"
    
    def test_path_patterns_override_extension(self):
        """Test that path patterns take precedence over extension."""
        from strix.tools.strixdb.strixdb_repo_extract import _categorize_file
        
        # Path pattern should override .txt -> wordlists
        # Note: patterns are checked in order, and "xss" maps to payloads before cheatsheet
        assert _categorize_file("cheatsheets/command_cheat.txt") == "cheatsheets"
        assert _categorize_file("techniques/ssrf.txt") == "techniques"


class TestExtractionManifest:
    """Tests for extraction manifest creation."""
    
    def test_create_manifest(self):
        """Test creating extraction manifest."""
        from strix.tools.strixdb.strixdb_repo_extract import _create_extraction_manifest
        
        manifest = _create_extraction_manifest(
            repo_url="https://github.com/owner/repo",
            repo_slug="owner_repo",
            description="Test repository",
            tags=["test", "bugbounty"],
        )
        
        assert manifest["repo_slug"] == "owner_repo"
        assert manifest["source_url"] == "https://github.com/owner/repo"
        assert manifest["description"] == "Test repository"
        assert manifest["tags"] == ["test", "bugbounty"]
        assert manifest["status"] == "initialized"
        assert "id" in manifest
        assert "created_at" in manifest
        assert "stats" in manifest
        assert "category_counts" in manifest
    
    def test_manifest_stats_structure(self):
        """Test manifest stats structure."""
        from strix.tools.strixdb.strixdb_repo_extract import _create_extraction_manifest
        
        manifest = _create_extraction_manifest(
            repo_url="https://github.com/owner/repo",
            repo_slug="owner_repo",
        )
        
        stats = manifest["stats"]
        assert stats["total_files_scanned"] == 0
        assert stats["files_extracted"] == 0
        assert stats["files_skipped"] == 0
        assert stats["total_size_bytes"] == 0
    
    def test_manifest_category_counts(self):
        """Test manifest category counts structure."""
        from strix.tools.strixdb.strixdb_repo_extract import _create_extraction_manifest
        
        manifest = _create_extraction_manifest(
            repo_url="https://github.com/owner/repo",
            repo_slug="owner_repo",
        )
        
        counts = manifest["category_counts"]
        assert "tools" in counts
        assert "scripts" in counts
        assert "wordlists" in counts
        assert "payloads" in counts
        assert "exploits" in counts
        assert "documentation" in counts


class TestRepoExtractInit:
    """Tests for strixdb_repo_extract_init function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    def test_init_without_config(self, mock_config, mock_agent_state):
        """Test init fails gracefully without config."""
        mock_config.return_value = {"repo": "", "token": ""}
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_init
        
        result = strixdb_repo_extract_init(
            mock_agent_state,
            repo_url="https://github.com/owner/repo",
        )
        
        assert result["success"] is False
        assert "not configured" in result["error"].lower()
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_init_existing_repo(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test init returns existing repo data."""
        mock_config.return_value = mock_strixdb_config
        
        existing_manifest = {
            "repo_slug": "owner_repo",
            "source_url": "https://github.com/owner/repo",
            "status": "completed",
            "stats": {"files_extracted": 50},
        }
        mock_get_file.return_value = (existing_manifest, "existing_sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_init
        
        result = strixdb_repo_extract_init(
            mock_agent_state,
            repo_url="https://github.com/owner/repo",
        )
        
        assert result["success"] is True
        assert result["is_new"] is False
        assert result["manifest"]["status"] == "completed"


class TestRepoExtractFile:
    """Tests for strixdb_repo_extract_file function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    def test_extract_file_not_found(self, mock_config, mock_agent_state, mock_strixdb_config):
        """Test extracting non-existent file."""
        mock_config.return_value = mock_strixdb_config
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_file
        
        result = strixdb_repo_extract_file(
            mock_agent_state,
            repo_slug="owner_repo",
            file_path="nonexistent.py",
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._save_repo_file')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="print('hello')")
    def test_extract_file_success(
        self,
        mock_file,
        mock_exists,
        mock_get_file,
        mock_save,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test successful file extraction."""
        mock_config.return_value = mock_strixdb_config
        mock_exists.return_value = True
        mock_save.return_value = True
        mock_get_file.return_value = ({"files": []}, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_file
        
        result = strixdb_repo_extract_file(
            mock_agent_state,
            repo_slug="owner_repo",
            file_path="script.py",
            custom_description="Test script",
        )
        
        assert result["success"] is True
        assert "item" in result
        # "script.py" - "script" in filename matches "tool|script|bin|util" pattern -> "tools"
        assert result["item"]["category"] == "tools"


class TestRepoExtractCategory:
    """Tests for strixdb_repo_extract_category function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_extract_category_no_index(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test extracting category without index."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({"files": []}, None)
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_category
        
        result = strixdb_repo_extract_category(
            mock_agent_state,
            repo_slug="owner_repo",
            category="scripts",
        )
        
        # Should fail because no index
        assert "error" in result or result.get("extracted_count", 0) == 0
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_extract_category_empty(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test extracting category with no matching files."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({
            "files": [
                {"path": "readme.md", "category": "documentation", "size": 100, "extracted": False}
            ]
        }, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_category
        
        result = strixdb_repo_extract_category(
            mock_agent_state,
            repo_slug="owner_repo",
            category="scripts",  # No scripts in index
        )
        
        assert result["success"] is True
        assert result["extracted_count"] == 0


class TestRepoExtractStatus:
    """Tests for strixdb_repo_extract_status function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_status_success(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test getting extraction status."""
        mock_config.return_value = mock_strixdb_config
        
        def get_file_side_effect(config, slug, filename, default):
            if filename == "manifest.json":
                return ({
                    "source_url": "https://github.com/owner/repo",
                    "status": "extracting",
                    "category_counts": {"scripts": 10, "wordlists": 20},
                    "extraction_history": [],
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_extraction_at": "2024-01-01T01:00:00Z",
                }, "sha1")
            elif filename == "index.json":
                return ({
                    "files": [
                        {"path": "a.py", "category": "scripts", "extracted": True},
                        {"path": "b.py", "category": "scripts", "extracted": True},
                        {"path": "c.py", "category": "scripts", "extracted": False},
                    ]
                }, "sha2")
            return (default, None)
        
        mock_get_file.side_effect = get_file_side_effect
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_status
        
        result = strixdb_repo_extract_status(
            mock_agent_state,
            repo_slug="owner_repo",
        )
        
        assert result["success"] is True
        assert result["status"] == "extracting"
        assert result["stats"]["total_files"] == 3
        assert result["stats"]["extracted"] == 2
        assert result["stats"]["pending"] == 1
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_status_not_found(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test status for non-existent repo."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({}, None)
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_status
        
        result = strixdb_repo_extract_status(
            mock_agent_state,
            repo_slug="nonexistent_repo",
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestRepoListExtracted:
    """Tests for strixdb_repo_list_extracted function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_list_extracted_success(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test listing extracted files."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({
            "files": [
                {"path": "a.py", "category": "scripts", "size": 100, "extracted": True, "extracted_to": "cat/a.json"},
                {"path": "b.py", "category": "scripts", "size": 200, "extracted": True, "extracted_to": "cat/b.json"},
                {"path": "c.py", "category": "scripts", "size": 300, "extracted": False},
            ]
        }, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_list_extracted
        
        result = strixdb_repo_list_extracted(
            mock_agent_state,
            repo_slug="owner_repo",
        )
        
        assert result["success"] is True
        assert result["total_extracted"] == 2
        assert len(result["items"]) == 2
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_list_extracted_by_category(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test listing extracted files filtered by category."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({
            "files": [
                {"path": "a.py", "category": "scripts", "extracted": True},
                {"path": "b.txt", "category": "wordlists", "extracted": True},
            ]
        }, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_list_extracted
        
        result = strixdb_repo_list_extracted(
            mock_agent_state,
            repo_slug="owner_repo",
            category="scripts",
        )
        
        assert result["success"] is True
        assert result["total_extracted"] == 1


class TestRepoGetItem:
    """Tests for strixdb_repo_get_item function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_get_item_success(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test getting a specific extracted item."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({
            "id": "ext_12345",
            "name": "test_script",
            "category": "scripts",
            "content": "print('hello')",
            "original_path": "test_script.py",
        }, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_get_item
        
        result = strixdb_repo_get_item(
            mock_agent_state,
            repo_slug="owner_repo",
            category="scripts",
            item_name="test_script",
        )
        
        assert result["success"] is True
        assert result["item"]["name"] == "test_script"
        assert result["item"]["content"] == "print('hello')"
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_get_item_not_found(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test getting non-existent item."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({}, None)
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_get_item
        
        result = strixdb_repo_get_item(
            mock_agent_state,
            repo_slug="owner_repo",
            category="scripts",
            item_name="nonexistent",
        )
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestRepoSearch:
    """Tests for strixdb_repo_search function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('requests.get')
    def test_search_success(
        self,
        mock_requests_get,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test searching across extracted repos."""
        mock_config.return_value = mock_strixdb_config
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_count": 2,
            "items": [
                {"path": "extracted_repos/owner_repo/categories/scripts/test.json", "score": 1.0},
                {"path": "extracted_repos/owner_repo/categories/wordlists/common.json", "score": 0.8},
            ],
        }
        mock_requests_get.return_value = mock_response
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_search
        
        result = strixdb_repo_search(
            mock_agent_state,
            query="test",
        )
        
        assert result["success"] is True
        assert result["total_count"] == 2
        assert len(result["results"]) == 2


class TestRepoList:
    """Tests for strixdb_repo_list function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('requests.get')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_list_repos_success(
        self,
        mock_get_file,
        mock_requests_get,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test listing all extracted repos."""
        mock_config.return_value = mock_strixdb_config
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"type": "dir", "name": "owner_repo"},
            {"type": "dir", "name": "another_repo"},
        ]
        mock_requests_get.return_value = mock_response
        
        mock_get_file.return_value = ({
            "source_url": "https://github.com/owner/repo",
            "status": "completed",
            "stats": {"files_extracted": 50},
            "category_counts": {"scripts": 10},
            "tags": ["bugbounty"],
            "created_at": "2024-01-01T00:00:00Z",
        }, "sha")
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_list
        
        result = strixdb_repo_list(mock_agent_state)
        
        assert result["success"] is True
        assert len(result["repositories"]) == 2
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('requests.get')
    def test_list_repos_empty(
        self,
        mock_requests_get,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test listing when no repos extracted."""
        mock_config.return_value = mock_strixdb_config
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_list
        
        result = strixdb_repo_list(mock_agent_state)
        
        assert result["success"] is True
        assert result["repositories"] == []


class TestExtractAll:
    """Tests for strixdb_repo_extract_all function."""
    
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_strixdb_config')
    @patch('strix.tools.strixdb.strixdb_repo_extract._get_or_create_repo_file')
    def test_extract_all_no_manifest(
        self,
        mock_get_file,
        mock_config,
        mock_agent_state,
        mock_strixdb_config,
    ):
        """Test extract all without manifest."""
        mock_config.return_value = mock_strixdb_config
        mock_get_file.return_value = ({}, None)
        
        from strix.tools.strixdb.strixdb_repo_extract import strixdb_repo_extract_all
        
        result = strixdb_repo_extract_all(
            mock_agent_state,
            repo_slug="nonexistent_repo",
        )
        
        assert result["success"] is False
        assert "not initialized" in result["error"].lower()


class TestFileTypeMappings:
    """Tests for file type mappings configuration."""
    
    def test_file_type_mappings_exist(self):
        """Test that file type mappings are defined."""
        from strix.tools.strixdb.strixdb_repo_extract import FILE_TYPE_MAPPINGS
        
        assert ".py" in FILE_TYPE_MAPPINGS
        assert ".sh" in FILE_TYPE_MAPPINGS
        assert ".md" in FILE_TYPE_MAPPINGS
        assert ".txt" in FILE_TYPE_MAPPINGS
        assert ".yml" in FILE_TYPE_MAPPINGS
    
    def test_path_patterns_exist(self):
        """Test that path patterns are defined."""
        from strix.tools.strixdb.strixdb_repo_extract import PATH_PATTERNS
        
        assert len(PATH_PATTERNS) > 0
        # Check some key patterns exist
        pattern_values = list(PATH_PATTERNS.values())
        assert "wordlists" in pattern_values
        assert "payloads" in pattern_values
        assert "exploits" in pattern_values
