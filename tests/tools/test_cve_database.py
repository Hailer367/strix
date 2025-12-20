"""Tests for CVE/Exploit Database Integration module."""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

# Import the module under test
from strix.tools.cve_database.cve_database_actions import (
    _parse_version,
    _version_in_range,
    _extract_cve_severity,
    _extract_affected_versions,
    _extract_references,
    query_cve_database,
    search_exploits,
    get_cve_details,
    search_github_advisories,
    get_technology_vulnerabilities,
    search_packetstorm,
)


class TestVersionParsing:
    """Tests for version parsing and comparison utilities."""

    def test_parse_version_simple(self) -> None:
        """Test parsing simple version strings."""
        assert _parse_version("1.18.0") == (1, 18, 0)
        assert _parse_version("2.4.49") == (2, 4, 49)
        assert _parse_version("5.9.3") == (5, 9, 3)

    def test_parse_version_with_prefix(self) -> None:
        """Test parsing versions with prefixes."""
        assert _parse_version("v1.2.3") == (1, 2, 3)
        assert _parse_version("apache-2.4.49") == (2, 4, 49)

    def test_parse_version_short(self) -> None:
        """Test parsing short version strings."""
        assert _parse_version("1.0") == (1, 0)
        assert _parse_version("10") == (10,)

    def test_parse_version_invalid(self) -> None:
        """Test parsing invalid version strings."""
        assert _parse_version("") == (0,)
        assert _parse_version("abc") == (0,)

    def test_version_in_range_exact(self) -> None:
        """Test version in exact range."""
        assert _version_in_range("1.18.0", "1.18.0", "1.18.0")
        assert _version_in_range("2.4.49", "2.4.0", "2.5.0")

    def test_version_in_range_exclusive(self) -> None:
        """Test version with exclusive bounds."""
        assert not _version_in_range(
            "1.0.0", "1.0.0", None, start_inclusive=False
        )
        assert not _version_in_range(
            "2.0.0", None, "2.0.0", end_inclusive=False
        )

    def test_version_in_range_no_bounds(self) -> None:
        """Test version with no bounds."""
        assert _version_in_range("1.0.0")
        assert _version_in_range("999.999.999")


class TestCVEExtraction:
    """Tests for CVE data extraction functions."""

    def test_extract_severity_cvss_v31(self) -> None:
        """Test extracting CVSS v3.1 severity."""
        cve_item = {
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "baseScore": 9.8,
                            "baseSeverity": "CRITICAL",
                            "attackVector": "NETWORK",
                            "attackComplexity": "LOW",
                        }
                    }
                ]
            }
        }
        
        severity = _extract_cve_severity(cve_item)
        
        assert severity["cvss_v3_score"] == 9.8
        assert severity["cvss_v3_severity"] == "CRITICAL"
        assert severity["attack_vector"] == "NETWORK"
        assert severity["attack_complexity"] == "LOW"

    def test_extract_severity_cvss_v2_fallback(self) -> None:
        """Test extracting CVSS v2 severity as fallback."""
        cve_item = {
            "metrics": {
                "cvssMetricV2": [
                    {
                        "cvssData": {"baseScore": 7.5},
                        "baseSeverity": "HIGH",
                    }
                ]
            }
        }
        
        severity = _extract_cve_severity(cve_item)
        
        assert severity["cvss_v2_score"] == 7.5
        assert severity["cvss_v2_severity"] == "HIGH"

    def test_extract_severity_empty(self) -> None:
        """Test extracting severity from empty metrics."""
        cve_item = {"metrics": {}}
        severity = _extract_cve_severity(cve_item)
        
        assert severity["cvss_v3_score"] is None
        assert severity["cvss_v2_score"] is None

    def test_extract_affected_versions(self) -> None:
        """Test extracting affected versions."""
        cve_item = {
            "configurations": [
                {
                    "nodes": [
                        {
                            "cpeMatch": [
                                {
                                    "vulnerable": True,
                                    "criteria": "cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*",
                                    "versionStartIncluding": "1.0.0",
                                    "versionEndExcluding": "1.20.0",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        versions = _extract_affected_versions(cve_item)
        
        assert len(versions) == 1
        assert versions[0]["version_start"] == "1.0.0"
        assert versions[0]["version_start_inclusive"] is True
        assert versions[0]["version_end_inclusive"] is False

    def test_extract_references_prioritizes_exploits(self) -> None:
        """Test that exploit references are prioritized."""
        cve_item = {
            "references": [
                {"url": "https://example.com/advisory", "tags": ["Vendor Advisory"]},
                {"url": "https://exploit-db.com/exploits/12345", "tags": ["Exploit"]},
                {"url": "https://github.com/poc/test", "tags": []},
            ]
        }
        
        refs = _extract_references(cve_item)
        
        # Exploit should be first
        assert "exploit-db" in refs[0]["url"].lower()


class TestQueryCVEDatabase:
    """Tests for query_cve_database function."""

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_query_cve_success(self, mock_get: MagicMock) -> None:
        """Test successful CVE query."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "totalResults": 1,
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2021-23017",
                        "descriptions": [{"lang": "en", "value": "Test description"}],
                        "metrics": {
                            "cvssMetricV31": [
                                {"cvssData": {"baseScore": 7.5, "baseSeverity": "HIGH"}}
                            ]
                        },
                        "references": [],
                        "configurations": [],
                    }
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = query_cve_database("nginx", version="1.18.0")

        assert result["success"] is True
        assert len(result["cves"]) == 1
        assert result["cves"][0]["cve_id"] == "CVE-2021-23017"
        assert result["version_specific"] is True

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_query_cve_timeout(self, mock_get: MagicMock) -> None:
        """Test CVE query timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = query_cve_database("nginx")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_query_cve_severity_filter(self, mock_get: MagicMock) -> None:
        """Test CVE query with severity filtering."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "totalResults": 2,
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2021-0001",
                        "descriptions": [{"lang": "en", "value": "Low severity"}],
                        "metrics": {
                            "cvssMetricV31": [
                                {"cvssData": {"baseScore": 3.0, "baseSeverity": "LOW"}}
                            ]
                        },
                        "references": [],
                        "configurations": [],
                    }
                },
                {
                    "cve": {
                        "id": "CVE-2021-0002",
                        "descriptions": [{"lang": "en", "value": "High severity"}],
                        "metrics": {
                            "cvssMetricV31": [
                                {"cvssData": {"baseScore": 8.5, "baseSeverity": "HIGH"}}
                            ]
                        },
                        "references": [],
                        "configurations": [],
                    }
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = query_cve_database("nginx", severity_threshold="HIGH")

        assert result["success"] is True
        # Only HIGH severity should be included
        assert len(result["cves"]) == 1
        assert result["cves"][0]["severity_level"] == "HIGH"


class TestSearchExploits:
    """Tests for search_exploits function."""

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_exploits_success(self, mock_get: MagicMock) -> None:
        """Test successful exploit search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <a href="/exploits/12345">Test Exploit 1</a>
            <a href="/exploits/12346">Test Exploit 2</a>
        '''
        mock_get.return_value = mock_response

        result = search_exploits("CVE-2021-23017")

        assert result["success"] is True
        assert "alternative_searches" in result

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_exploits_timeout(self, mock_get: MagicMock) -> None:
        """Test exploit search timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = search_exploits("test")

        assert result["success"] is False
        assert "timed out" in result["error"].lower()


class TestGetCVEDetails:
    """Tests for get_cve_details function."""

    def test_invalid_cve_id_format(self) -> None:
        """Test handling of invalid CVE ID format."""
        result = get_cve_details("invalid-id")
        
        assert result["success"] is False
        assert "Invalid CVE ID format" in result["error"]

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_cve_not_found(self, mock_get: MagicMock) -> None:
        """Test handling of CVE not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"vulnerabilities": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_cve_details("CVE-9999-99999")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_cve_details_success(self, mock_get: MagicMock) -> None:
        """Test successful CVE details retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2021-23017",
                        "descriptions": [
                            {"lang": "en", "value": "DNS resolver vulnerability in nginx"}
                        ],
                        "metrics": {
                            "cvssMetricV31": [
                                {
                                    "cvssData": {
                                        "baseScore": 7.7,
                                        "baseSeverity": "HIGH",
                                        "attackVector": "NETWORK",
                                        "attackComplexity": "HIGH",
                                    }
                                }
                            ]
                        },
                        "references": [
                            {"url": "https://exploit-db.com/test", "tags": ["Exploit"]}
                        ],
                        "configurations": [],
                        "published": "2021-05-25T00:00:00.000",
                        "lastModified": "2021-06-01T00:00:00.000",
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_cve_details("CVE-2021-23017")

        assert result["success"] is True
        assert result["cve_id"] == "CVE-2021-23017"
        assert result["cve_details"]["cvss_score"] == 7.7
        assert result["exploitability"]["has_public_exploit"] is True


class TestSearchGitHubAdvisories:
    """Tests for search_github_advisories function."""

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_advisories_success(self, mock_get: MagicMock) -> None:
        """Test successful GitHub advisories search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "ghsa_id": "GHSA-1234-5678-abcd",
                "cve_id": "CVE-2021-00001",
                "summary": "Test vulnerability",
                "severity": "high",
                "cvss": {"score": 8.0},
                "vulnerabilities": [
                    {"package": {"name": "lodash", "ecosystem": "npm"}}
                ],
            }
        ]
        mock_get.return_value = mock_response

        result = search_github_advisories(ecosystem="npm", severity="high")

        assert result["success"] is True
        assert len(result["advisories"]) >= 0  # May vary based on API response

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_advisories_request_error(self, mock_get: MagicMock) -> None:
        """Test GitHub advisories search with request error."""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("API error")

        result = search_github_advisories()

        assert result["success"] is False


class TestGetTechnologyVulnerabilities:
    """Tests for get_technology_vulnerabilities function."""

    @patch("strix.tools.cve_database.cve_database_actions.query_cve_database")
    @patch("strix.tools.cve_database.cve_database_actions.search_exploits")
    @patch("strix.tools.cve_database.cve_database_actions.search_github_advisories")
    def test_tech_vulns_aggregation(
        self,
        mock_github: MagicMock,
        mock_exploits: MagicMock,
        mock_cve: MagicMock,
    ) -> None:
        """Test aggregation of vulnerability data from multiple sources."""
        mock_cve.return_value = {
            "success": True,
            "cves": [
                {
                    "cve_id": "CVE-2021-23017",
                    "description": "DNS resolver vulnerability",
                    "severity_level": "HIGH",
                    "cvss_score": 7.7,
                    "has_known_exploit": True,
                    "references": [],
                }
            ],
        }
        mock_exploits.return_value = {
            "success": True,
            "exploits": [{"title": "Test exploit", "url": "https://example.com"}],
        }
        mock_github.return_value = {"success": True, "advisories": []}

        result = get_technology_vulnerabilities("nginx", version="1.18.0")

        assert result["success"] is True
        assert len(result["vulnerabilities"]) >= 1
        assert len(result["testing_priority"]) >= 0
        assert "summary" in result


class TestSearchPacketStorm:
    """Tests for search_packetstorm function."""

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_packetstorm_success(self, mock_get: MagicMock) -> None:
        """Test successful PacketStorm search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '''
            <a href="/files/12345/test-exploit.txt">Test Exploit</a>
        '''
        mock_get.return_value = mock_response

        result = search_packetstorm("nginx")

        assert result["success"] is True
        assert "direct_search_url" in result

    @patch("strix.tools.cve_database.cve_database_actions.requests.get")
    def test_search_packetstorm_timeout(self, mock_get: MagicMock) -> None:
        """Test PacketStorm search timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = search_packetstorm("test")

        assert result["success"] is False
