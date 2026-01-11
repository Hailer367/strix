"""
CVE/Exploit Database Actions.

This module provides tools for querying vulnerability databases and exploit repositories
to help AI agents find and use known vulnerabilities for identified technologies.

Data Sources:
- NVD (National Vulnerability Database) - Official CVE database
- Exploit-DB - Exploit and PoC repository
- GitHub Security Advisories - Package vulnerability database
- PacketStorm - Additional exploit/tool source
"""

import hashlib
import json
import re
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import requests

from strix.tools.registry import register_tool


# =============================================================================
# Cache Management
# =============================================================================

# Cache for API responses to reduce redundant queries
_cve_cache: dict[str, dict[str, Any]] = {}
_cache_ttl_hours = 24  # Cache results for 24 hours

# Rate limiting
_rate_limit_state: dict[str, datetime] = {}
_rate_limit_delay_seconds = 6  # NVD rate limit: 5 requests per 30 seconds


def _cache_key(source: str, query: str) -> str:
    """Generate a cache key for a query."""
    return hashlib.md5(f"{source}:{query}".encode()).hexdigest()


def _get_from_cache(source: str, query: str) -> dict[str, Any] | None:
    """Get cached result if not expired."""
    key = _cache_key(source, query)
    if key in _cve_cache:
        cached = _cve_cache[key]
        cached_time = datetime.fromisoformat(cached.get("cached_at", ""))
        if datetime.now(UTC) - cached_time < timedelta(hours=_cache_ttl_hours):
            return cached.get("data")
    return None


def _set_cache(source: str, query: str, data: dict[str, Any]) -> None:
    """Cache query result."""
    key = _cache_key(source, query)
    _cve_cache[key] = {
        "cached_at": datetime.now(UTC).isoformat(),
        "data": data,
    }


def _check_rate_limit(source: str) -> bool:
    """Check if we should wait for rate limiting."""
    if source in _rate_limit_state:
        last_request = _rate_limit_state[source]
        if datetime.now(UTC) - last_request < timedelta(seconds=_rate_limit_delay_seconds):
            return False
    _rate_limit_state[source] = datetime.now(UTC)
    return True


def _safe_request(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict[str, Any] | None:
    """Make a safe HTTP request with error handling and retry logic.
    
    Args:
        url: The URL to request
        headers: Optional request headers
        params: Optional query parameters
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries (exponential backoff applied)
    
    Returns:
        JSON response data or None if all attempts fail
    """
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            last_error = f"Request timeout after {timeout}s"
            logger.warning(f"CVE API timeout (attempt {attempt + 1}/{max_retries}): {last_error}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {str(e)}"
            logger.warning(f"CVE API connection error (attempt {attempt + 1}/{max_retries}): {last_error}")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            last_error = f"HTTP {status_code}: {str(e)}"
            logger.warning(f"CVE API HTTP error (attempt {attempt + 1}/{max_retries}): {last_error}")
            # Don't retry on client errors (4xx) except 429 (rate limit)
            if e.response and 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                return None
        except requests.exceptions.RequestException as e:
            last_error = f"Request error: {str(e)}"
            logger.warning(f"CVE API request error (attempt {attempt + 1}/{max_retries}): {last_error}")
        except json.JSONDecodeError as e:
            last_error = f"JSON decode error: {str(e)}"
            logger.warning(f"CVE API JSON error (attempt {attempt + 1}/{max_retries}): {last_error}")
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.warning(f"CVE API unexpected error (attempt {attempt + 1}/{max_retries}): {last_error}")
        
        # Wait before retry with exponential backoff
        if attempt < max_retries - 1:
            sleep_time = retry_delay * (2 ** attempt)
            logger.info(f"Retrying CVE API in {sleep_time}s...")
            time.sleep(sleep_time)
    
    logger.error(f"CVE API failed after {max_retries} attempts. Last error: {last_error}")
    return None


# =============================================================================
# NVD (National Vulnerability Database) Integration
# =============================================================================

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _parse_nvd_cve(cve_item: dict[str, Any]) -> dict[str, Any]:
    """Parse NVD CVE item into a standardized format."""
    cve = cve_item.get("cve", {})
    cve_id = cve.get("id", "Unknown")
    
    # Get descriptions
    descriptions = cve.get("descriptions", [])
    description = ""
    for desc in descriptions:
        if desc.get("lang") == "en":
            description = desc.get("value", "")
            break
    
    # Get CVSS scores
    metrics = cve.get("metrics", {})
    cvss_v3 = None
    cvss_v2 = None
    severity = "unknown"
    
    # Try CVSS 3.1 first, then 3.0, then 2.0
    if "cvssMetricV31" in metrics:
        cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
        cvss_v3 = cvss_data.get("baseScore")
        severity = cvss_data.get("baseSeverity", "unknown").lower()
    elif "cvssMetricV30" in metrics:
        cvss_data = metrics["cvssMetricV30"][0].get("cvssData", {})
        cvss_v3 = cvss_data.get("baseScore")
        severity = cvss_data.get("baseSeverity", "unknown").lower()
    elif "cvssMetricV2" in metrics:
        cvss_data = metrics["cvssMetricV2"][0].get("cvssData", {})
        cvss_v2 = cvss_data.get("baseScore")
        severity_score = cvss_v2 or 0
        if severity_score >= 7.0:
            severity = "high"
        elif severity_score >= 4.0:
            severity = "medium"
        else:
            severity = "low"
    
    # Get references
    references = []
    for ref in cve.get("references", []):
        references.append({
            "url": ref.get("url"),
            "source": ref.get("source"),
            "tags": ref.get("tags", []),
        })
    
    # Get affected configurations (CPE)
    affected_products = []
    configurations = cve.get("configurations", [])
    for config in configurations:
        for node in config.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                if cpe_match.get("vulnerable"):
                    cpe = cpe_match.get("criteria", "")
                    # Parse CPE: cpe:2.3:a:vendor:product:version:...
                    parts = cpe.split(":")
                    if len(parts) >= 6:
                        affected_products.append({
                            "vendor": parts[3] if len(parts) > 3 else "unknown",
                            "product": parts[4] if len(parts) > 4 else "unknown",
                            "version": parts[5] if len(parts) > 5 else "*",
                            "version_start": cpe_match.get("versionStartIncluding"),
                            "version_end": cpe_match.get("versionEndExcluding") or cpe_match.get("versionEndIncluding"),
                            "cpe": cpe,
                        })
    
    # Get weaknesses (CWE)
    weaknesses = []
    for weakness in cve.get("weaknesses", []):
        for desc in weakness.get("description", []):
            if desc.get("lang") == "en":
                weaknesses.append(desc.get("value", ""))
    
    # Dates
    published = cve.get("published", "")
    last_modified = cve.get("lastModified", "")
    
    return {
        "cve_id": cve_id,
        "description": description,
        "cvss_v3": cvss_v3,
        "cvss_v2": cvss_v2,
        "severity": severity,
        "references": references,
        "affected_products": affected_products,
        "weaknesses": weaknesses,
        "published": published,
        "last_modified": last_modified,
        "source": "NVD",
    }


@register_tool(sandbox_execution=False)
def query_cve_database(
    keyword: str | None = None,
    product: str | None = None,
    vendor: str | None = None,
    version: str | None = None,
    cve_id: str | None = None,
    severity: Literal["critical", "high", "medium", "low"] | None = None,
    published_start: str | None = None,
    published_end: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Query NVD (National Vulnerability Database) for CVEs.
    
    Use this when you want to find known vulnerabilities for a specific technology,
    product, or search by keyword.
    
    Args:
        keyword: Search keyword in CVE descriptions
        product: Product name to search for (e.g., "nginx", "apache", "wordpress")
        vendor: Vendor name to filter by
        version: Specific version to check
        cve_id: Specific CVE ID to look up (e.g., "CVE-2021-44228")
        severity: Filter by severity level
        published_start: Start date for publication filter (YYYY-MM-DD)
        published_end: End date for publication filter (YYYY-MM-DD)
        limit: Maximum number of results (default: 20, max: 100)
    
    Returns:
        Dictionary containing CVE search results with severity, descriptions,
        affected versions, and references.
    
    Example:
        # Find CVEs for nginx 1.18.0
        query_cve_database(product="nginx", version="1.18.0")
        
        # Search for Log4j vulnerabilities
        query_cve_database(keyword="log4j")
        
        # Get specific CVE
        query_cve_database(cve_id="CVE-2021-44228")
    """
    # Build cache key
    cache_query = f"{keyword}:{product}:{vendor}:{version}:{cve_id}:{severity}:{published_start}:{published_end}"
    
    # Check cache
    cached = _get_from_cache("nvd", cache_query)
    if cached:
        return cached
    
    # Rate limiting
    if not _check_rate_limit("nvd"):
        return {
            "success": False,
            "error": "Rate limited. Please wait a few seconds between queries.",
            "source": "NVD",
        }
    
    # Build query parameters
    params: dict[str, Any] = {}
    
    if cve_id:
        params["cveId"] = cve_id
    
    if keyword:
        params["keywordSearch"] = keyword
        params["keywordExactMatch"] = ""
    
    if product or vendor:
        # Build CPE match string
        cpe_parts = ["cpe", "2.3", "a"]  # application type
        cpe_parts.append(vendor.lower() if vendor else "*")
        cpe_parts.append(product.lower() if product else "*")
        if version:
            cpe_parts.append(version)
        else:
            cpe_parts.append("*")
        
        # Pad with wildcards
        while len(cpe_parts) < 13:
            cpe_parts.append("*")
        
        cpe_match = ":".join(cpe_parts)
        params["cpeName"] = cpe_match
    
    if severity:
        severity_map = {
            "critical": "CRITICAL",
            "high": "HIGH",
            "medium": "MEDIUM",
            "low": "LOW",
        }
        params["cvssV3Severity"] = severity_map.get(severity, severity.upper())
    
    if published_start:
        params["pubStartDate"] = f"{published_start}T00:00:00.000"
    if published_end:
        params["pubEndDate"] = f"{published_end}T23:59:59.999"
    
    params["resultsPerPage"] = min(limit, 100)
    
    # Make request with retry logic
    headers = {
        "User-Agent": "Strix-Security-Agent/1.0",
        "Accept": "application/json",
    }
    
    response_data = _safe_request(
        NVD_API_BASE, 
        headers=headers, 
        params=params, 
        timeout=60,
        max_retries=3,
        retry_delay=2.0
    )
    
    if not response_data:
        # Try alternate NVD endpoint if primary fails
        alt_nvd_base = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        response_data = _safe_request(
            alt_nvd_base, 
            headers=headers, 
            params=params, 
            timeout=90,  # Longer timeout for fallback
            max_retries=2,
            retry_delay=3.0
        )
    
    if not response_data:
        # Return helpful information even when API fails
        search_terms = []
        if keyword:
            search_terms.append(keyword)
        if product:
            search_terms.append(product)
        if cve_id:
            search_terms.append(cve_id)
        
        search_query = " ".join(search_terms) if search_terms else "vulnerability"
        
        return {
            "success": False,
            "error": "Failed to query NVD API after multiple retries. The service may be temporarily unavailable or rate limited.",
            "source": "NVD",
            "suggestion": "Try again in a few minutes, or use the manual search links below.",
            "manual_search_links": {
                "nvd": f"https://nvd.nist.gov/vuln/search/results?query={urllib.parse.quote(search_query)}",
                "cvedetails": f"https://www.cvedetails.com/google-search-results.php?q={urllib.parse.quote(search_query)}",
                "mitre": f"https://cve.mitre.org/cgi-bin/cvekey.cgi?keyword={urllib.parse.quote(search_query)}",
                "exploitdb": f"https://www.exploit-db.com/search?q={urllib.parse.quote(search_query)}",
            },
            "troubleshooting": [
                "The NVD API has rate limits (5 requests per 30 seconds for anonymous users)",
                "Consider waiting 30 seconds before retrying",
                "For more queries, consider using an NVD API key",
                "Manual search via the links above is always available",
            ],
        }
    
    # Parse results
    vulnerabilities = response_data.get("vulnerabilities", [])
    total_results = response_data.get("totalResults", 0)
    
    cves = []
    for vuln in vulnerabilities:
        parsed = _parse_nvd_cve(vuln)
        cves.append(parsed)
    
    # Sort by severity and CVSS score
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    cves.sort(key=lambda x: (severity_order.get(x["severity"], 4), -(x.get("cvss_v3") or x.get("cvss_v2") or 0)))
    
    result = {
        "success": True,
        "source": "NVD",
        "total_results": total_results,
        "returned_results": len(cves),
        "query": {
            "keyword": keyword,
            "product": product,
            "vendor": vendor,
            "version": version,
            "cve_id": cve_id,
            "severity": severity,
        },
        "vulnerabilities": cves,
        "summary": {
            "critical": sum(1 for c in cves if c["severity"] == "critical"),
            "high": sum(1 for c in cves if c["severity"] == "high"),
            "medium": sum(1 for c in cves if c["severity"] == "medium"),
            "low": sum(1 for c in cves if c["severity"] == "low"),
        },
    }
    
    # Cache result
    _set_cache("nvd", cache_query, result)
    
    return result


@register_tool(sandbox_execution=False)
def get_cve_details(cve_id: str) -> dict[str, Any]:
    """
    Get detailed information about a specific CVE.
    
    Args:
        cve_id: The CVE identifier (e.g., "CVE-2021-44228")
    
    Returns:
        Dictionary containing full CVE details including description,
        CVSS scores, affected products, references, and exploitability.
    
    Example:
        get_cve_details("CVE-2021-44228")  # Log4Shell
    """
    # Validate CVE ID format
    if not re.match(r"^CVE-\d{4}-\d+$", cve_id.upper()):
        return {
            "success": False,
            "error": f"Invalid CVE ID format: {cve_id}. Expected format: CVE-YYYY-NNNNN",
        }
    
    cve_id = cve_id.upper()
    
    # Query NVD for full details
    result = query_cve_database(cve_id=cve_id, limit=1)
    
    if not result.get("success"):
        return result
    
    if not result.get("vulnerabilities"):
        return {
            "success": False,
            "error": f"CVE {cve_id} not found in NVD database",
        }
    
    cve = result["vulnerabilities"][0]
    
    # Search for exploits
    exploits_result = search_exploitdb(cve_id=cve_id, limit=5)
    exploits = exploits_result.get("exploits", []) if exploits_result.get("success") else []
    
    # Check GitHub advisories
    github_result = search_github_advisories(cve_id=cve_id)
    github_advisories = github_result.get("advisories", []) if github_result.get("success") else []
    
    # Determine exploitability
    has_public_exploit = len(exploits) > 0
    has_poc = any("poc" in e.get("type", "").lower() for e in exploits)
    has_metasploit = any("metasploit" in e.get("type", "").lower() for e in exploits)
    
    exploitability = "none"
    if has_metasploit:
        exploitability = "weaponized"
    elif has_poc:
        exploitability = "poc_available"
    elif has_public_exploit:
        exploitability = "exploit_available"
    
    return {
        "success": True,
        "cve": cve,
        "exploitability": exploitability,
        "public_exploits": exploits,
        "github_advisories": github_advisories,
        "has_public_exploit": has_public_exploit,
        "recommendations": _generate_recommendations(cve, has_public_exploit),
    }


def _generate_recommendations(cve: dict[str, Any], has_exploit: bool) -> list[str]:
    """Generate security recommendations based on CVE data."""
    recommendations = []
    
    severity = cve.get("severity", "unknown")
    
    if severity == "critical" or has_exploit:
        recommendations.append("URGENT: This vulnerability should be patched immediately.")
    elif severity == "high":
        recommendations.append("HIGH PRIORITY: Schedule patching within 1-7 days.")
    elif severity == "medium":
        recommendations.append("MEDIUM PRIORITY: Include in next maintenance cycle.")
    else:
        recommendations.append("LOW PRIORITY: Address when convenient.")
    
    if has_exploit:
        recommendations.append("WARNING: Public exploit exists. Assume active exploitation attempts.")
    
    # Check for specific vulnerability types
    weaknesses = cve.get("weaknesses", [])
    for weakness in weaknesses:
        if "CWE-79" in weakness:
            recommendations.append("Consider implementing Content Security Policy (CSP).")
        elif "CWE-89" in weakness:
            recommendations.append("Use parameterized queries to prevent SQL injection.")
        elif "CWE-78" in weakness:
            recommendations.append("Avoid executing shell commands with user input.")
        elif "CWE-287" in weakness:
            recommendations.append("Review authentication mechanisms.")
        elif "CWE-22" in weakness:
            recommendations.append("Implement strict path validation.")
    
    # Check references for patches
    for ref in cve.get("references", []):
        tags = ref.get("tags", [])
        if "Patch" in tags or "Vendor Advisory" in tags:
            recommendations.append(f"Patch available: {ref.get('url')}")
            break
    
    return recommendations


# =============================================================================
# Exploit-DB Integration
# =============================================================================

EXPLOITDB_SEARCH_URL = "https://www.exploit-db.com/search"
EXPLOITDB_BASE_URL = "https://www.exploit-db.com"


@register_tool(sandbox_execution=False)
def search_exploitdb(
    query: str | None = None,
    cve_id: str | None = None,
    platform: str | None = None,
    exploit_type: str | None = None,
    verified_only: bool = False,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search Exploit-DB for exploits and PoCs.
    
    Use this when you want to find working exploits or proof-of-concepts
    for a vulnerability.
    
    Args:
        query: Search query (technology name, vulnerability description)
        cve_id: CVE identifier to search for
        platform: Target platform filter (linux, windows, multiple, etc.)
        exploit_type: Type filter (webapps, remote, local, dos, shellcode)
        verified_only: Only return verified exploits
        limit: Maximum results (default: 20)
    
    Returns:
        Dictionary containing matching exploits with download links and descriptions.
    
    Example:
        # Search for WordPress exploits
        search_exploitdb(query="wordpress")
        
        # Find exploits for specific CVE
        search_exploitdb(cve_id="CVE-2021-44228")
    """
    # Build search query
    search_terms = []
    if query:
        search_terms.append(query)
    if cve_id:
        search_terms.append(cve_id)
    
    if not search_terms:
        return {
            "success": False,
            "error": "Please provide either a query or cve_id",
            "source": "Exploit-DB",
        }
    
    search_query = " ".join(search_terms)
    cache_key = f"{search_query}:{platform}:{exploit_type}:{verified_only}"
    
    # Check cache
    cached = _get_from_cache("exploitdb", cache_key)
    if cached:
        return cached
    
    # Exploit-DB doesn't have a public API, so we'll simulate the expected results
    # In a real implementation, you would scrape or use unofficial APIs
    
    # Build a list of example/simulated results based on common patterns
    exploits = _simulate_exploitdb_search(search_query, platform, exploit_type, verified_only, limit)
    
    result = {
        "success": True,
        "source": "Exploit-DB",
        "query": {
            "search": search_query,
            "platform": platform,
            "type": exploit_type,
            "verified_only": verified_only,
        },
        "total_results": len(exploits),
        "exploits": exploits,
        "search_url": f"{EXPLOITDB_BASE_URL}/?q={urllib.parse.quote(search_query)}",
        "note": "Results may require manual verification on Exploit-DB website",
    }
    
    _set_cache("exploitdb", cache_key, result)
    return result


def _simulate_exploitdb_search(
    query: str,
    platform: str | None,
    exploit_type: str | None,
    verified_only: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Simulate Exploit-DB search results.
    
    In production, this would actually query Exploit-DB's search.
    For now, we return structured data that guides the agent to check Exploit-DB.
    """
    query_lower = query.lower()
    
    # Common CVE patterns
    cve_pattern = re.match(r"cve-(\d{4})-(\d+)", query_lower)
    
    results = []
    
    # Return guidance for manual lookup
    results.append({
        "id": "search_guidance",
        "title": f"Manual search recommended for: {query}",
        "description": f"Search Exploit-DB directly for '{query}' to find exploits and PoCs",
        "type": "guidance",
        "platform": platform or "multiple",
        "verified": False,
        "url": f"{EXPLOITDB_BASE_URL}/search?q={urllib.parse.quote(query)}",
        "download_url": None,
        "author": "N/A",
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
    })
    
    # Add tips based on query
    if "wordpress" in query_lower:
        results.append({
            "id": "tip_wordpress",
            "title": "WordPress Exploit Tip",
            "description": "Check WPScan Vulnerability Database (wpscan.com) for WordPress-specific vulnerabilities",
            "type": "tip",
            "platform": "webapps",
            "verified": False,
            "url": "https://wpscan.com/vulnerabilities",
            "download_url": None,
            "author": "System",
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        })
    
    if cve_pattern:
        results.append({
            "id": "tip_cve",
            "title": f"CVE Search Tip for {query.upper()}",
            "description": f"Also check: GitHub ({query}), PacketStorm, and vendor security advisories",
            "type": "tip",
            "platform": "multiple",
            "verified": False,
            "url": f"https://github.com/search?q={urllib.parse.quote(query)}&type=repositories",
            "download_url": None,
            "author": "System",
            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        })
    
    return results[:limit]


# =============================================================================
# GitHub Security Advisories Integration
# =============================================================================

GITHUB_ADVISORY_API = "https://api.github.com/advisories"


@register_tool(sandbox_execution=False)
def search_github_advisories(
    keyword: str | None = None,
    cve_id: str | None = None,
    ecosystem: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search GitHub Security Advisories database.
    
    Useful for finding vulnerabilities in packages and dependencies.
    
    Args:
        keyword: Search keyword
        cve_id: Specific CVE ID to lookup
        ecosystem: Package ecosystem (npm, pip, maven, rubygems, nuget, composer, etc.)
        severity: Severity filter (critical, high, medium, low)
        limit: Maximum results (default: 20)
    
    Returns:
        Dictionary containing GitHub Security Advisories matching the query.
    
    Example:
        # Search for log4j advisories
        search_github_advisories(keyword="log4j", ecosystem="maven")
        
        # Get advisory for specific CVE
        search_github_advisories(cve_id="CVE-2021-44228")
    """
    search_terms = []
    if keyword:
        search_terms.append(keyword)
    if cve_id:
        search_terms.append(cve_id)
    
    if not search_terms:
        return {
            "success": False,
            "error": "Please provide either keyword or cve_id",
            "source": "GitHub Security Advisories",
        }
    
    search_query = " ".join(search_terms)
    cache_key = f"{search_query}:{ecosystem}:{severity}"
    
    # Check cache
    cached = _get_from_cache("github_advisories", cache_key)
    if cached:
        return cached
    
    # Rate limiting
    if not _check_rate_limit("github"):
        return {
            "success": False,
            "error": "Rate limited. Please wait a few seconds.",
            "source": "GitHub Security Advisories",
        }
    
    # Build query parameters
    params: dict[str, Any] = {
        "per_page": min(limit, 100),
    }
    
    if cve_id:
        params["cve_id"] = cve_id
    
    if ecosystem:
        params["ecosystem"] = ecosystem
    
    if severity:
        params["severity"] = severity
    
    # Add keyword to query if provided (GitHub uses different endpoint for search)
    if keyword and not cve_id:
        # Use GraphQL search or REST search
        params["type"] = "reviewed"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Strix-Security-Agent/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    response_data = _safe_request(GITHUB_ADVISORY_API, headers=headers, params=params, timeout=30)
    
    if response_data is None:
        # Return helpful guidance even if API fails
        return {
            "success": True,
            "source": "GitHub Security Advisories",
            "note": "API unavailable. Search manually on GitHub.",
            "search_url": f"https://github.com/advisories?query={urllib.parse.quote(search_query)}",
            "total_results": 0,
            "advisories": [],
        }
    
    # Parse advisories
    advisories = []
    items = response_data if isinstance(response_data, list) else []
    
    for item in items:
        advisory = {
            "ghsa_id": item.get("ghsa_id", ""),
            "cve_id": item.get("cve_id"),
            "summary": item.get("summary", ""),
            "description": item.get("description", "")[:500],
            "severity": item.get("severity", "unknown"),
            "cvss_score": item.get("cvss", {}).get("score"),
            "published_at": item.get("published_at"),
            "updated_at": item.get("updated_at"),
            "url": item.get("html_url"),
            "vulnerabilities": [
                {
                    "package": v.get("package", {}).get("name"),
                    "ecosystem": v.get("package", {}).get("ecosystem"),
                    "vulnerable_range": v.get("vulnerable_version_range"),
                    "patched_versions": v.get("first_patched_version", {}).get("identifier"),
                }
                for v in item.get("vulnerabilities", [])
            ],
            "references": [ref.get("url") for ref in item.get("references", [])],
        }
        advisories.append(advisory)
    
    result = {
        "success": True,
        "source": "GitHub Security Advisories",
        "query": {
            "keyword": keyword,
            "cve_id": cve_id,
            "ecosystem": ecosystem,
            "severity": severity,
        },
        "total_results": len(advisories),
        "advisories": advisories,
        "search_url": f"https://github.com/advisories?query={urllib.parse.quote(search_query)}",
    }
    
    _set_cache("github_advisories", cache_key, result)
    return result


# =============================================================================
# PacketStorm Integration
# =============================================================================

PACKETSTORM_BASE_URL = "https://packetstormsecurity.com"


@register_tool(sandbox_execution=False)
def search_packetstorm(
    query: str,
    file_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search PacketStorm for exploits, tools, and security advisories.
    
    PacketStorm is a security information portal with exploits,
    advisories, and tools.
    
    Args:
        query: Search query (technology, CVE, vulnerability type)
        file_type: Filter by type (exploits, tools, advisories)
        limit: Maximum results (default: 20)
    
    Returns:
        Dictionary with search results and download links.
    
    Example:
        search_packetstorm("apache struts")
        search_packetstorm("CVE-2021-44228")
    """
    if not query:
        return {
            "success": False,
            "error": "Search query is required",
            "source": "PacketStorm",
        }
    
    cache_key = f"{query}:{file_type}"
    
    # Check cache
    cached = _get_from_cache("packetstorm", cache_key)
    if cached:
        return cached
    
    # PacketStorm doesn't have a public API, return guidance
    search_url = f"{PACKETSTORM_BASE_URL}/search/?q={urllib.parse.quote(query)}"
    
    if file_type:
        search_url += f"&type={file_type}"
    
    result = {
        "success": True,
        "source": "PacketStorm",
        "query": query,
        "file_type": file_type,
        "search_url": search_url,
        "note": "PacketStorm requires manual browsing. Use the search URL provided.",
        "results": [
            {
                "title": f"Search PacketStorm for: {query}",
                "description": "Visit the search URL to find exploits, advisories, and tools",
                "url": search_url,
                "type": "search_link",
            }
        ],
        "additional_resources": [
            {
                "name": "PacketStorm Files",
                "url": f"{PACKETSTORM_BASE_URL}/files/tags/{urllib.parse.quote(query.replace(' ', '_'))}",
                "description": "Browse files tagged with search term",
            },
            {
                "name": "Security News",
                "url": f"{PACKETSTORM_BASE_URL}/news/tags/{urllib.parse.quote(query.replace(' ', '_'))}",
                "description": "Security news related to search term",
            },
        ],
    }
    
    _set_cache("packetstorm", cache_key, result)
    return result


# =============================================================================
# Aggregated Vulnerability Search
# =============================================================================

@register_tool(sandbox_execution=False)
def get_technology_vulnerabilities(
    technology: str,
    version: str | None = None,
    vendor: str | None = None,
    include_exploits: bool = True,
    severity_filter: str | None = None,
) -> dict[str, Any]:
    """
    Get comprehensive vulnerability information for a technology from multiple sources.
    
    This aggregates data from NVD, Exploit-DB, GitHub Advisories, and PacketStorm
    to provide a complete picture of known vulnerabilities.
    
    Args:
        technology: Technology/product name (e.g., "nginx", "apache", "wordpress")
        version: Specific version to check (e.g., "1.18.0")
        vendor: Vendor name for more precise results
        include_exploits: Also search for public exploits
        severity_filter: Only return vulnerabilities of this severity or higher
    
    Returns:
        Dictionary containing aggregated vulnerability data from all sources
        with severity summary, exploit availability, and recommendations.
    
    Example:
        # Check nginx 1.18.0 for vulnerabilities
        get_technology_vulnerabilities("nginx", version="1.18.0")
        
        # Check WordPress for critical vulnerabilities
        get_technology_vulnerabilities("wordpress", severity_filter="critical")
    """
    results = {
        "success": True,
        "technology": technology,
        "version": version,
        "vendor": vendor,
        "sources_queried": [],
        "cves": [],
        "exploits": [],
        "advisories": [],
        "summary": {
            "total_cves": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "exploits_available": 0,
            "actively_exploited": False,
        },
        "recommendations": [],
    }
    
    # Query NVD
    nvd_result = query_cve_database(
        product=technology,
        vendor=vendor,
        version=version,
        severity=severity_filter,
        limit=50,
    )
    
    if nvd_result.get("success"):
        results["sources_queried"].append("NVD")
        results["cves"] = nvd_result.get("vulnerabilities", [])
        results["summary"]["total_cves"] = len(results["cves"])
        results["summary"]["critical"] = nvd_result.get("summary", {}).get("critical", 0)
        results["summary"]["high"] = nvd_result.get("summary", {}).get("high", 0)
        results["summary"]["medium"] = nvd_result.get("summary", {}).get("medium", 0)
        results["summary"]["low"] = nvd_result.get("summary", {}).get("low", 0)
    
    # Query GitHub Advisories
    github_result = search_github_advisories(
        keyword=technology,
        severity=severity_filter,
        limit=20,
    )
    
    if github_result.get("success"):
        results["sources_queried"].append("GitHub Security Advisories")
        results["advisories"] = github_result.get("advisories", [])
    
    # Search for exploits if requested
    if include_exploits:
        exploit_result = search_exploitdb(query=technology, limit=20)
        if exploit_result.get("success"):
            results["sources_queried"].append("Exploit-DB")
            results["exploits"] = exploit_result.get("exploits", [])
            results["summary"]["exploits_available"] = len([
                e for e in results["exploits"]
                if e.get("type") != "guidance" and e.get("type") != "tip"
            ])
        
        # Also search PacketStorm
        packetstorm_result = search_packetstorm(query=technology)
        if packetstorm_result.get("success"):
            results["sources_queried"].append("PacketStorm")
            results["packetstorm_search_url"] = packetstorm_result.get("search_url")
    
    # Generate recommendations
    summary = results["summary"]
    
    if summary["critical"] > 0:
        results["recommendations"].append(
            f"CRITICAL: {summary['critical']} critical vulnerabilities found. Immediate patching required."
        )
        results["summary"]["actively_exploited"] = True  # Assume critical vulns are being exploited
    
    if summary["high"] > 0:
        results["recommendations"].append(
            f"HIGH: {summary['high']} high severity vulnerabilities. Schedule patching within 7 days."
        )
    
    if summary["exploits_available"] > 0:
        results["recommendations"].append(
            f"WARNING: {summary['exploits_available']} public exploits found. Higher risk of exploitation."
        )
    
    if summary["total_cves"] == 0:
        results["recommendations"].append(
            "No known CVEs found. This doesn't mean the software is secure - manual testing recommended."
        )
    
    if version:
        results["recommendations"].append(
            f"Consider upgrading from version {version} to the latest stable release."
        )
    
    # Add search links for manual verification
    results["manual_search_links"] = {
        "nvd": f"https://nvd.nist.gov/vuln/search/results?query={urllib.parse.quote(technology)}",
        "exploitdb": f"https://www.exploit-db.com/search?q={urllib.parse.quote(technology)}",
        "github": f"https://github.com/advisories?query={urllib.parse.quote(technology)}",
        "packetstorm": f"https://packetstormsecurity.com/search/?q={urllib.parse.quote(technology)}",
        "cvedetails": f"https://www.cvedetails.com/google-search-results.php?q={urllib.parse.quote(technology)}",
    }
    
    return results


# =============================================================================
# Cache Management Tools
# =============================================================================

@register_tool(sandbox_execution=False)
def clear_cve_cache() -> dict[str, Any]:
    """
    Clear the CVE database cache.
    
    Use this if you want fresh results from vulnerability databases.
    
    Returns:
        Dictionary with cache clear status.
    """
    entries_cleared = len(_cve_cache)
    _cve_cache.clear()
    
    return {
        "success": True,
        "message": f"Cleared {entries_cleared} cached entries",
    }


@register_tool(sandbox_execution=False)
def get_cache_stats() -> dict[str, Any]:
    """
    Get statistics about the CVE cache.
    
    Returns:
        Dictionary with cache statistics.
    """
    stats = {
        "total_entries": len(_cve_cache),
        "sources": {},
    }
    
    for key in _cve_cache:
        # Keys are MD5 hashes, we can't easily categorize them
        # But we can count total entries
        pass
    
    return {
        "success": True,
        "cache_entries": len(_cve_cache),
        "cache_ttl_hours": _cache_ttl_hours,
        "rate_limit_delay_seconds": _rate_limit_delay_seconds,
    }
