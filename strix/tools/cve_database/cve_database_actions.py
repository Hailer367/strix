"""CVE/Exploit Database Integration Actions.

Provides tools for querying multiple vulnerability databases to help
AI agents find and use known vulnerabilities for identified technologies.
"""

import logging
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import requests

from strix.tools.registry import register_tool


logger = logging.getLogger(__name__)

# API Configuration
NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
EXPLOITDB_API_BASE = "https://www.exploit-db.com"
GITHUB_API_BASE = "https://api.github.com"
PACKETSTORM_BASE = "https://packetstormsecurity.com"

# Timeout for API requests
API_TIMEOUT = 30


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison."""
    try:
        # Extract numeric parts from version string
        parts = re.findall(r"\d+", version_str)
        return tuple(int(p) for p in parts[:4])  # Limit to 4 parts
    except (ValueError, AttributeError):
        return (0,)


def _version_in_range(
    version: str,
    start_version: str | None = None,
    end_version: str | None = None,
    start_inclusive: bool = True,
    end_inclusive: bool = True,
) -> bool:
    """Check if a version falls within a specified range."""
    try:
        v = _parse_version(version)

        if start_version:
            start_v = _parse_version(start_version)
            if start_inclusive:
                if v < start_v:
                    return False
            elif v <= start_v:
                return False

        if end_version:
            end_v = _parse_version(end_version)
            if end_inclusive:
                if v > end_v:
                    return False
            elif v >= end_v:
                return False

        return True
    except (ValueError, TypeError):
        return True  # If we can't parse, assume vulnerable


def _extract_cve_severity(cve_item: dict[str, Any]) -> dict[str, Any]:
    """Extract CVSS severity information from CVE item."""
    severity_info = {
        "cvss_v3_score": None,
        "cvss_v3_severity": None,
        "cvss_v2_score": None,
        "cvss_v2_severity": None,
        "attack_vector": None,
        "attack_complexity": None,
        "privileges_required": None,
        "user_interaction": None,
    }

    metrics = cve_item.get("metrics", {})

    # Try CVSS v3.1 first
    cvss_v31 = metrics.get("cvssMetricV31", [])
    if cvss_v31:
        cvss_data = cvss_v31[0].get("cvssData", {})
        severity_info["cvss_v3_score"] = cvss_data.get("baseScore")
        severity_info["cvss_v3_severity"] = cvss_data.get("baseSeverity")
        severity_info["attack_vector"] = cvss_data.get("attackVector")
        severity_info["attack_complexity"] = cvss_data.get("attackComplexity")
        severity_info["privileges_required"] = cvss_data.get("privilegesRequired")
        severity_info["user_interaction"] = cvss_data.get("userInteraction")

    # Try CVSS v3.0
    cvss_v30 = metrics.get("cvssMetricV30", [])
    if cvss_v30 and not severity_info["cvss_v3_score"]:
        cvss_data = cvss_v30[0].get("cvssData", {})
        severity_info["cvss_v3_score"] = cvss_data.get("baseScore")
        severity_info["cvss_v3_severity"] = cvss_data.get("baseSeverity")

    # Try CVSS v2
    cvss_v2 = metrics.get("cvssMetricV2", [])
    if cvss_v2:
        cvss_data = cvss_v2[0].get("cvssData", {})
        severity_info["cvss_v2_score"] = cvss_data.get("baseScore")
        severity_info["cvss_v2_severity"] = cvss_v2[0].get("baseSeverity")

    return severity_info


def _extract_affected_versions(cve_item: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract affected version information from CVE configurations."""
    affected_versions = []

    configurations = cve_item.get("configurations", [])
    for config in configurations:
        nodes = config.get("nodes", [])
        for node in nodes:
            cpe_matches = node.get("cpeMatch", [])
            for match in cpe_matches:
                if match.get("vulnerable", False):
                    cpe_uri = match.get("criteria", "")
                    version_info = {
                        "cpe": cpe_uri,
                        "version_start": match.get("versionStartIncluding")
                        or match.get("versionStartExcluding"),
                        "version_end": match.get("versionEndIncluding")
                        or match.get("versionEndExcluding"),
                        "version_start_inclusive": "versionStartIncluding" in match,
                        "version_end_inclusive": "versionEndIncluding" in match,
                    }
                    affected_versions.append(version_info)

    return affected_versions


def _extract_references(cve_item: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract references from CVE item, prioritizing exploits and PoCs."""
    references = []
    exploit_refs = []
    poc_refs = []
    advisory_refs = []
    other_refs = []

    for ref in cve_item.get("references", []):
        ref_info = {
            "url": ref.get("url", ""),
            "source": ref.get("source", ""),
            "tags": ref.get("tags", []),
        }

        tags_lower = [t.lower() for t in ref.get("tags", [])]

        if "exploit" in tags_lower or "exploit-db" in ref.get("url", "").lower():
            exploit_refs.append(ref_info)
        elif (
            "poc" in tags_lower
            or "proof-of-concept" in ref.get("url", "").lower()
            or "github.com" in ref.get("url", "").lower()
        ):
            poc_refs.append(ref_info)
        elif "vendor advisory" in tags_lower or "patch" in tags_lower:
            advisory_refs.append(ref_info)
        else:
            other_refs.append(ref_info)

    # Prioritize exploits and PoCs
    references = exploit_refs + poc_refs + advisory_refs + other_refs

    return references[:10]  # Limit to 10 most relevant references


@register_tool(sandbox_execution=False)
def query_cve_database(
    keyword: str,
    version: str | None = None,
    severity_threshold: str = "LOW",
    max_results: int = 20,
) -> dict[str, Any]:
    """Query the NVD (National Vulnerability Database) for CVEs affecting a technology.

    This tool searches NVD for known vulnerabilities based on keyword (product name)
    and optionally filters by version and severity.

    Args:
        keyword: Technology/product name to search (e.g., "nginx", "wordpress", "apache")
        version: Specific version to check (e.g., "1.18.0"). If provided, filters
                 results to only CVEs affecting this version.
        severity_threshold: Minimum CVSS severity to include. Options: LOW, MEDIUM, HIGH, CRITICAL
        max_results: Maximum number of CVEs to return (default: 20)

    Returns:
        Dictionary containing:
        - success: Whether the query was successful
        - cves: List of CVE entries with details
        - total_found: Total CVEs found matching criteria
        - version_specific: Whether results are filtered by version
        - query_info: Information about the search performed
    """
    try:
        # Build NVD API query
        params = {
            "keywordSearch": keyword,
            "resultsPerPage": min(max_results * 2, 100),  # Get extra for filtering
        }

        # Add NVD API key if available for higher rate limits
        nvd_api_key = os.getenv("NVD_API_KEY")
        headers = {}
        if nvd_api_key:
            headers["apiKey"] = nvd_api_key

        logger.info(f"Querying NVD for: {keyword} (version: {version})")

        response = requests.get(
            NVD_API_BASE, params=params, headers=headers, timeout=API_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()
        vulnerabilities = data.get("vulnerabilities", [])

        # Severity mapping for filtering
        severity_order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        threshold_level = severity_order.get(severity_threshold.upper(), 1)

        processed_cves = []

        for vuln in vulnerabilities:
            cve_item = vuln.get("cve", {})
            cve_id = cve_item.get("id", "Unknown")

            # Extract severity
            severity = _extract_cve_severity(cve_item)

            # Filter by severity threshold
            cve_severity = severity.get("cvss_v3_severity") or severity.get(
                "cvss_v2_severity"
            )
            if cve_severity:
                cve_level = severity_order.get(cve_severity.upper(), 0)
                if cve_level < threshold_level:
                    continue

            # Extract affected versions
            affected_versions = _extract_affected_versions(cve_item)

            # If version specified, check if it's affected
            version_affected = True
            if version and affected_versions:
                version_affected = False
                for av in affected_versions:
                    if _version_in_range(
                        version,
                        av.get("version_start"),
                        av.get("version_end"),
                        av.get("version_start_inclusive", True),
                        av.get("version_end_inclusive", True),
                    ):
                        version_affected = True
                        break

            if not version_affected:
                continue

            # Extract description
            descriptions = cve_item.get("descriptions", [])
            description = ""
            for desc in descriptions:
                if desc.get("lang") == "en":
                    description = desc.get("value", "")
                    break

            # Extract references
            references = _extract_references(cve_item)

            # Check for known exploits in references
            has_exploit = any(
                "exploit" in str(ref.get("tags", [])).lower()
                or "exploit-db" in ref.get("url", "").lower()
                for ref in references
            )

            processed_cves.append(
                {
                    "cve_id": cve_id,
                    "description": description[:500]
                    + ("..." if len(description) > 500 else ""),
                    "severity": severity,
                    "cvss_score": severity.get("cvss_v3_score")
                    or severity.get("cvss_v2_score"),
                    "severity_level": cve_severity,
                    "affected_versions": affected_versions[:5],  # Limit for readability
                    "references": references[:5],  # Top 5 references
                    "has_known_exploit": has_exploit,
                    "published_date": cve_item.get("published", ""),
                    "last_modified": cve_item.get("lastModified", ""),
                }
            )

            if len(processed_cves) >= max_results:
                break

        # Sort by severity score (highest first)
        processed_cves.sort(key=lambda x: x.get("cvss_score") or 0, reverse=True)

        return {
            "success": True,
            "cves": processed_cves,
            "total_found": len(processed_cves),
            "total_in_database": data.get("totalResults", 0),
            "version_specific": version is not None,
            "query_info": {
                "keyword": keyword,
                "version": version,
                "severity_threshold": severity_threshold,
            },
            "recommendations": [
                f"Found {len(processed_cves)} CVEs for {keyword}"
                + (f" version {version}" if version else ""),
                "CVEs with 'has_known_exploit: true' have publicly available exploits",
                "Check the references for exploit code and PoCs",
                "Higher CVSS scores indicate more severe vulnerabilities",
            ],
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "NVD API request timed out",
            "cves": [],
            "suggestion": "Try again with a more specific keyword",
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"NVD API request failed: {e!s}",
            "cves": [],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error querying CVE database: {e}")
        return {
            "success": False,
            "error": f"Failed to query CVE database: {e!s}",
            "cves": [],
        }


@register_tool(sandbox_execution=False)
def search_exploits(
    search_term: str,
    exploit_type: str | None = None,
    platform: str | None = None,
    max_results: int = 15,
) -> dict[str, Any]:
    """Search Exploit-DB for exploits and PoCs.

    This tool searches the Exploit Database for exploit code, PoCs, and
    vulnerability details. Great for finding working exploits for known CVEs.

    Args:
        search_term: Search term (CVE ID, product name, or vulnerability type)
                     Examples: "CVE-2021-23017", "wordpress plugin", "sql injection nginx"
        exploit_type: Filter by exploit type. Options: "webapps", "remote", "local",
                      "dos", "shellcode", "papers"
        platform: Filter by platform. Options: "linux", "windows", "php", "python", etc.
        max_results: Maximum results to return (default: 15)

    Returns:
        Dictionary containing:
        - success: Whether the search was successful
        - exploits: List of exploit entries with details and download links
        - total_found: Number of exploits found
        - search_info: Information about the search performed
    """
    try:
        # Build search URL using Exploit-DB's search API endpoint
        # Note: Exploit-DB has rate limiting, so we'll use their CSV search
        search_url = f"{EXPLOITDB_API_BASE}/search"

        params = {"q": search_term}

        if exploit_type:
            params["type"] = exploit_type
        if platform:
            params["platform"] = platform

        headers = {
            "User-Agent": "Strix Security Scanner/1.0",
            "Accept": "application/json, text/html",
        }

        logger.info(f"Searching Exploit-DB for: {search_term}")

        # Try to get results from Exploit-DB
        response = requests.get(
            search_url, params=params, headers=headers, timeout=API_TIMEOUT
        )

        exploits = []

        # Parse HTML response (Exploit-DB returns HTML for search)
        if response.status_code == 200:
            content = response.text

            # Extract exploit entries using regex patterns
            # Pattern for exploit IDs and titles
            exploit_pattern = r'href="/exploits/(\d+)"[^>]*>([^<]+)</a>'
            matches = re.findall(exploit_pattern, content)

            for exploit_id, title in matches[:max_results]:
                exploits.append(
                    {
                        "exploit_id": exploit_id,
                        "title": title.strip(),
                        "url": f"{EXPLOITDB_API_BASE}/exploits/{exploit_id}",
                        "raw_url": f"{EXPLOITDB_API_BASE}/raw/{exploit_id}",
                        "download_url": f"{EXPLOITDB_API_BASE}/download/{exploit_id}",
                    }
                )

        # If we couldn't parse enough results, provide alternative search suggestions
        if len(exploits) < 3:
            # Add GitHub search as fallback
            github_exploits = _search_github_for_exploits(search_term, max_results=5)
            if github_exploits:
                exploits.extend(github_exploits)

        return {
            "success": True,
            "exploits": exploits[:max_results],
            "total_found": len(exploits),
            "search_info": {
                "search_term": search_term,
                "exploit_type": exploit_type,
                "platform": platform,
            },
            "usage_tips": [
                "Use 'raw_url' to get the exploit source code directly",
                "CVE IDs work best for finding specific exploits",
                "Combine product name with vulnerability type for better results",
                "Example: 'wordpress sqli' or 'nginx buffer overflow'",
            ],
            "alternative_searches": [
                f"https://www.exploit-db.com/search?q={quote_plus(search_term)}",
                f"https://github.com/search?q={quote_plus(search_term)}+exploit&type=repositories",
                f"https://www.rapid7.com/db/?q={quote_plus(search_term)}",
            ],
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Exploit-DB request timed out",
            "exploits": [],
            "alternative_searches": [
                f"https://www.exploit-db.com/search?q={quote_plus(search_term)}",
            ],
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Exploit-DB request failed: {e!s}",
            "exploits": [],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error searching exploits: {e}")
        return {
            "success": False,
            "error": f"Failed to search exploits: {e!s}",
            "exploits": [],
        }


def _search_github_for_exploits(search_term: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search GitHub for exploit repositories as fallback."""
    try:
        github_token = os.getenv("GITHUB_TOKEN")
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Strix-Security-Scanner",
        }
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        # Search for exploit/PoC repositories
        search_query = f"{search_term} exploit OR poc OR vulnerability"
        params = {
            "q": search_query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results,
        }

        response = requests.get(
            f"{GITHUB_API_BASE}/search/repositories",
            params=params,
            headers=headers,
            timeout=API_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            exploits = []
            for repo in data.get("items", []):
                exploits.append(
                    {
                        "exploit_id": f"github-{repo.get('id')}",
                        "title": repo.get("full_name", ""),
                        "description": (repo.get("description") or "")[:200],
                        "url": repo.get("html_url", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "source": "github",
                    }
                )
            return exploits
    except Exception:  # noqa: BLE001
        pass
    return []


@register_tool(sandbox_execution=False)
def get_cve_details(cve_id: str) -> dict[str, Any]:
    """Get detailed information about a specific CVE.

    This tool retrieves comprehensive details about a CVE including:
    - Full description and impact
    - CVSS scores and severity metrics
    - Affected products and versions
    - References, patches, and exploit links

    Args:
        cve_id: The CVE identifier (e.g., "CVE-2021-23017", "CVE-2024-1234")

    Returns:
        Dictionary containing:
        - success: Whether the lookup was successful
        - cve_details: Comprehensive CVE information
        - exploit_info: Known exploit availability
        - remediation: Patch and mitigation information
    """
    try:
        # Validate CVE ID format
        cve_pattern = r"^CVE-\d{4}-\d{4,}$"
        if not re.match(cve_pattern, cve_id.upper()):
            return {
                "success": False,
                "error": f"Invalid CVE ID format: {cve_id}. Expected format: CVE-YYYY-NNNNN",
            }

        cve_id = cve_id.upper()

        # Query NVD for CVE details
        params = {"cveId": cve_id}

        nvd_api_key = os.getenv("NVD_API_KEY")
        headers = {}
        if nvd_api_key:
            headers["apiKey"] = nvd_api_key

        logger.info(f"Fetching details for: {cve_id}")

        response = requests.get(
            NVD_API_BASE, params=params, headers=headers, timeout=API_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()
        vulnerabilities = data.get("vulnerabilities", [])

        if not vulnerabilities:
            return {
                "success": False,
                "error": f"CVE {cve_id} not found in NVD",
                "suggestion": "The CVE may be very recent or reserved. Try searching Exploit-DB.",
            }

        cve_item = vulnerabilities[0].get("cve", {})

        # Extract full description
        descriptions = cve_item.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break

        # Extract severity information
        severity = _extract_cve_severity(cve_item)

        # Extract affected products/versions
        affected_versions = _extract_affected_versions(cve_item)

        # Extract and categorize references
        all_references = cve_item.get("references", [])
        exploit_refs = []
        poc_refs = []
        patch_refs = []
        advisory_refs = []

        for ref in all_references:
            url = ref.get("url", "")
            tags = [t.lower() for t in ref.get("tags", [])]

            ref_info = {"url": url, "tags": ref.get("tags", [])}

            if "exploit" in tags or "exploit-db.com" in url.lower():
                exploit_refs.append(ref_info)
            elif "github.com" in url.lower() and any(
                k in url.lower() for k in ["poc", "exploit", "vulnerability"]
            ):
                poc_refs.append(ref_info)
            elif "patch" in tags or "vendor advisory" in tags:
                patch_refs.append(ref_info)
            else:
                advisory_refs.append(ref_info)

        # Determine exploitability
        exploitability = {
            "has_public_exploit": len(exploit_refs) > 0,
            "has_poc": len(poc_refs) > 0,
            "has_patch": len(patch_refs) > 0,
            "exploit_count": len(exploit_refs) + len(poc_refs),
        }

        # Build remediation info
        remediation = {
            "patches_available": len(patch_refs) > 0,
            "patch_links": [ref["url"] for ref in patch_refs[:5]],
            "recommendations": [],
        }

        if severity.get("cvss_v3_severity") == "CRITICAL":
            remediation["recommendations"].append(
                "CRITICAL: Immediate patching recommended"
            )
        if exploitability["has_public_exploit"]:
            remediation["recommendations"].append(
                "Public exploits available - high priority for patching"
            )
        if not remediation["patches_available"]:
            remediation["recommendations"].append(
                "No patches found - consider workarounds or WAF rules"
            )

        return {
            "success": True,
            "cve_id": cve_id,
            "cve_details": {
                "description": description,
                "published_date": cve_item.get("published", ""),
                "last_modified": cve_item.get("lastModified", ""),
                "severity": severity,
                "cvss_score": severity.get("cvss_v3_score")
                or severity.get("cvss_v2_score"),
                "severity_level": severity.get("cvss_v3_severity")
                or severity.get("cvss_v2_severity"),
                "attack_vector": severity.get("attack_vector"),
                "attack_complexity": severity.get("attack_complexity"),
                "privileges_required": severity.get("privileges_required"),
                "user_interaction": severity.get("user_interaction"),
            },
            "affected_products": affected_versions[:10],
            "exploitability": exploitability,
            "exploit_references": exploit_refs[:5],
            "poc_references": poc_refs[:5],
            "remediation": remediation,
            "all_references": (advisory_refs + patch_refs)[:10],
            "testing_recommendations": [
                "Search for PoC code in exploit references",
                "Check GitHub for working exploits",
                "Review attack vector and complexity for manual testing",
                f"CVSS Attack Vector: {severity.get('attack_vector', 'Unknown')}",
            ],
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "NVD API request timed out"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"NVD API request failed: {e!s}"}
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error getting CVE details: {e}")
        return {"success": False, "error": f"Failed to get CVE details: {e!s}"}


@register_tool(sandbox_execution=False)
def search_github_advisories(
    ecosystem: str | None = None,
    package: str | None = None,
    severity: str | None = None,
    keyword: str | None = None,
    max_results: int = 15,
) -> dict[str, Any]:
    """Search GitHub Security Advisories database.

    This tool searches GitHub's security advisory database which contains
    vulnerabilities in open source packages. Great for finding vulnerabilities
    in npm, pip, Maven, and other package ecosystems.

    Args:
        ecosystem: Package ecosystem to search. Options: "npm", "pip", "maven",
                   "nuget", "go", "rubygems", "composer", "rust"
        package: Specific package name to search (e.g., "lodash", "requests")
        severity: Filter by severity. Options: "low", "medium", "high", "critical"
        keyword: Free-text keyword search (e.g., "prototype pollution", "rce")
        max_results: Maximum results to return (default: 15)

    Returns:
        Dictionary containing:
        - success: Whether the search was successful
        - advisories: List of security advisories with CVE links
        - total_found: Number of advisories found
    """
    try:
        # Build GraphQL query for GitHub Security Advisories
        github_token = os.getenv("GITHUB_TOKEN")

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Strix-Security-Scanner",
        }

        if github_token:
            headers["Authorization"] = f"token {github_token}"

        # Use REST API for searching advisories
        params = {"per_page": max_results}

        # Build search query
        query_parts = []
        if ecosystem:
            query_parts.append(f"ecosystem:{ecosystem}")
        if package:
            query_parts.append(package)
        if severity:
            query_parts.append(f"severity:{severity}")
        if keyword:
            query_parts.append(keyword)

        # If no specific filters, search for recent critical/high advisories
        if not query_parts:
            query_parts.append("severity:critical")

        params["q"] = " ".join(query_parts)

        logger.info(f"Searching GitHub advisories: {params['q']}")

        # Try the security advisories endpoint
        advisories_url = f"{GITHUB_API_BASE}/advisories"

        response = requests.get(
            advisories_url, params=params, headers=headers, timeout=API_TIMEOUT
        )

        advisories = []

        if response.status_code == 200:
            data = response.json()

            for adv in data:
                advisory_info = {
                    "ghsa_id": adv.get("ghsa_id", ""),
                    "cve_id": adv.get("cve_id"),
                    "summary": adv.get("summary", ""),
                    "description": (adv.get("description") or "")[:300],
                    "severity": adv.get("severity", ""),
                    "cvss_score": adv.get("cvss", {}).get("score"),
                    "published_at": adv.get("published_at", ""),
                    "updated_at": adv.get("updated_at", ""),
                    "url": adv.get("html_url", ""),
                    "vulnerabilities": [],
                }

                # Extract affected package info
                for vuln in adv.get("vulnerabilities", [])[:3]:
                    package_info = vuln.get("package", {})
                    advisory_info["vulnerabilities"].append(
                        {
                            "package": package_info.get("name", ""),
                            "ecosystem": package_info.get("ecosystem", ""),
                            "vulnerable_versions": vuln.get(
                                "vulnerable_version_range", ""
                            ),
                            "patched_versions": vuln.get("first_patched_version", {}),
                        }
                    )

                advisories.append(advisory_info)

        return {
            "success": True,
            "advisories": advisories,
            "total_found": len(advisories),
            "search_info": {
                "ecosystem": ecosystem,
                "package": package,
                "severity": severity,
                "keyword": keyword,
            },
            "usage_tips": [
                "Use ecosystem filter for package manager specific searches",
                "Combine package name with vulnerability keywords",
                "Check 'vulnerable_versions' to confirm if target is affected",
                "GHSA IDs can be cross-referenced with CVE IDs",
            ],
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"GitHub API request failed: {e!s}",
            "advisories": [],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error searching GitHub advisories: {e}")
        return {
            "success": False,
            "error": f"Failed to search GitHub advisories: {e!s}",
            "advisories": [],
        }


@register_tool(sandbox_execution=False)
def get_technology_vulnerabilities(
    technology: str,
    version: str | None = None,
    vuln_types: str | None = None,
    include_exploits: bool = True,
    max_results: int = 20,
) -> dict[str, Any]:
    """Get comprehensive vulnerability information for a specific technology.

    This is a high-level tool that aggregates vulnerability data from multiple
    sources (NVD, Exploit-DB, GitHub) for a given technology. Use this when
    you've identified a technology/version and want to find all known vulns.

    Args:
        technology: Technology name (e.g., "nginx", "wordpress", "apache tomcat")
        version: Specific version to check (e.g., "1.18.0", "5.9.3")
        vuln_types: Comma-separated vulnerability types to focus on
                    (e.g., "rce,sqli,xss,ssrf,lfi,xxe")
        include_exploits: Whether to search for available exploits (default: True)
        max_results: Maximum total results to return (default: 20)

    Returns:
        Dictionary containing:
        - success: Whether the search was successful
        - vulnerabilities: Aggregated list of vulnerabilities
        - exploits_available: Exploits found for these vulnerabilities
        - attack_surface: Summary of potential attack vectors
        - testing_priority: Prioritized list of vulnerabilities to test
    """
    try:
        logger.info(f"Getting vulnerabilities for: {technology} {version or ''}")

        results = {
            "success": True,
            "technology": technology,
            "version": version,
            "vulnerabilities": [],
            "exploits_available": [],
            "attack_surface": [],
            "testing_priority": [],
        }

        # 1. Query NVD for CVEs
        cve_results = query_cve_database(
            keyword=technology,
            version=version,
            severity_threshold="LOW",
            max_results=max_results,
        )

        if cve_results.get("success"):
            for cve in cve_results.get("cves", []):
                vuln_info = {
                    "source": "NVD",
                    "id": cve.get("cve_id"),
                    "description": cve.get("description"),
                    "severity": cve.get("severity_level"),
                    "cvss_score": cve.get("cvss_score"),
                    "has_exploit": cve.get("has_known_exploit", False),
                    "references": cve.get("references", []),
                }
                results["vulnerabilities"].append(vuln_info)

                if cve.get("has_known_exploit"):
                    results["exploits_available"].append(
                        {
                            "cve_id": cve.get("cve_id"),
                            "severity": cve.get("severity_level"),
                            "references": [
                                r
                                for r in cve.get("references", [])
                                if "exploit" in str(r).lower()
                            ],
                        }
                    )

        # 2. Search for exploits if requested
        if include_exploits:
            search_terms = [technology]
            if version:
                search_terms.append(f"{technology} {version}")

            for term in search_terms:
                exploit_results = search_exploits(
                    search_term=term, max_results=max_results // 2
                )

                if exploit_results.get("success"):
                    for exp in exploit_results.get("exploits", []):
                        results["exploits_available"].append(
                            {
                                "title": exp.get("title"),
                                "url": exp.get("url"),
                                "source": exp.get("source", "exploit-db"),
                            }
                        )

        # 3. Check GitHub advisories if it's a package
        github_results = search_github_advisories(
            keyword=technology, max_results=max_results // 2
        )

        if github_results.get("success"):
            for adv in github_results.get("advisories", []):
                vuln_info = {
                    "source": "GitHub",
                    "id": adv.get("ghsa_id") or adv.get("cve_id"),
                    "description": adv.get("summary"),
                    "severity": adv.get("severity"),
                    "cvss_score": adv.get("cvss_score"),
                    "has_exploit": False,
                    "url": adv.get("url"),
                }
                results["vulnerabilities"].append(vuln_info)

        # 4. Analyze attack surface based on vuln types
        vuln_type_keywords = {
            "rce": ["remote code execution", "command injection", "code execution"],
            "sqli": ["sql injection", "sqli"],
            "xss": ["cross-site scripting", "xss"],
            "ssrf": ["server-side request forgery", "ssrf"],
            "lfi": ["local file inclusion", "path traversal", "directory traversal"],
            "xxe": ["xml external entity", "xxe"],
            "auth": ["authentication bypass", "authorization", "access control"],
            "dos": ["denial of service", "dos", "resource exhaustion"],
        }

        if vuln_types:
            requested_types = [t.strip().lower() for t in vuln_types.split(",")]
        else:
            requested_types = list(vuln_type_keywords.keys())

        for vuln in results["vulnerabilities"]:
            desc_lower = (vuln.get("description") or "").lower()
            for vuln_type, keywords in vuln_type_keywords.items():
                if vuln_type in requested_types:
                    if any(kw in desc_lower for kw in keywords):
                        results["attack_surface"].append(
                            {
                                "vuln_type": vuln_type.upper(),
                                "cve_id": vuln.get("id"),
                                "severity": vuln.get("severity"),
                            }
                        )

        # 5. Build testing priority list
        # Sort by: 1) has exploit, 2) severity, 3) CVSS score
        severity_priority = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

        for vuln in results["vulnerabilities"]:
            priority_score = 0
            if vuln.get("has_exploit"):
                priority_score += 100
            priority_score += severity_priority.get(
                (vuln.get("severity") or "").upper(), 0
            ) * 10
            priority_score += vuln.get("cvss_score") or 0

            results["testing_priority"].append(
                {
                    "id": vuln.get("id"),
                    "severity": vuln.get("severity"),
                    "has_exploit": vuln.get("has_exploit"),
                    "priority_score": priority_score,
                    "recommendation": (
                        "HIGH PRIORITY - Exploit available"
                        if vuln.get("has_exploit")
                        else f"Test for {vuln.get('severity', 'Unknown')} severity vuln"
                    ),
                }
            )

        # Sort by priority score
        results["testing_priority"].sort(
            key=lambda x: x.get("priority_score", 0), reverse=True
        )
        results["testing_priority"] = results["testing_priority"][:10]

        # Remove duplicates from attack surface
        seen_attacks = set()
        unique_attacks = []
        for attack in results["attack_surface"]:
            key = (attack["vuln_type"], attack["cve_id"])
            if key not in seen_attacks:
                seen_attacks.add(key)
                unique_attacks.append(attack)
        results["attack_surface"] = unique_attacks[:10]

        # Summary statistics
        results["summary"] = {
            "total_vulnerabilities": len(results["vulnerabilities"]),
            "with_exploits": len(
                [v for v in results["vulnerabilities"] if v.get("has_exploit")]
            ),
            "critical_count": len(
                [
                    v
                    for v in results["vulnerabilities"]
                    if (v.get("severity") or "").upper() == "CRITICAL"
                ]
            ),
            "high_count": len(
                [
                    v
                    for v in results["vulnerabilities"]
                    if (v.get("severity") or "").upper() == "HIGH"
                ]
            ),
            "attack_vectors": list(set(a["vuln_type"] for a in results["attack_surface"])),
        }

        return results

    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error getting technology vulnerabilities: {e}")
        return {
            "success": False,
            "error": f"Failed to get technology vulnerabilities: {e!s}",
            "vulnerabilities": [],
        }


@register_tool(sandbox_execution=False)
def search_packetstorm(
    search_term: str,
    search_type: str = "files",
    max_results: int = 15,
) -> dict[str, Any]:
    """Search PacketStorm Security for exploits, tools, and security papers.

    PacketStorm is a comprehensive security resource with exploits, advisories,
    and tools. This search provides access to their archive of security content.

    Args:
        search_term: Search term (CVE ID, product name, vulnerability type)
        search_type: Type of content to search. Options:
                     - "files": Exploits and tools (default)
                     - "papers": Security papers and research
                     - "news": Security news
        max_results: Maximum results to return (default: 15)

    Returns:
        Dictionary containing:
        - success: Whether the search was successful
        - results: List of matching content with download links
        - total_found: Number of results found
    """
    try:
        # Build PacketStorm search URL
        search_url = f"{PACKETSTORM_BASE}/search/"

        params = {"q": search_term}

        headers = {
            "User-Agent": "Strix Security Scanner/1.0",
            "Accept": "text/html",
        }

        logger.info(f"Searching PacketStorm for: {search_term}")

        response = requests.get(
            search_url, params=params, headers=headers, timeout=API_TIMEOUT
        )

        results_list = []

        if response.status_code == 200:
            content = response.text

            # Extract result entries from HTML
            # Pattern to match file entries
            file_pattern = r'<a\s+href="(/files/\d+/[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(file_pattern, content)

            for path, title in matches[:max_results]:
                results_list.append(
                    {
                        "title": title.strip(),
                        "url": f"{PACKETSTORM_BASE}{path}",
                        "type": search_type,
                    }
                )

        return {
            "success": True,
            "results": results_list,
            "total_found": len(results_list),
            "search_info": {
                "search_term": search_term,
                "search_type": search_type,
            },
            "direct_search_url": f"{PACKETSTORM_BASE}/search/?q={quote_plus(search_term)}",
            "tips": [
                "PacketStorm often has exploit code not found elsewhere",
                "Check the file details page for download links",
                "Recent exploits are usually on the first page",
            ],
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"PacketStorm request failed: {e!s}",
            "results": [],
            "direct_search_url": f"{PACKETSTORM_BASE}/search/?q={quote_plus(search_term)}",
        }
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error searching PacketStorm: {e}")
        return {
            "success": False,
            "error": f"Failed to search PacketStorm: {e!s}",
            "results": [],
        }
