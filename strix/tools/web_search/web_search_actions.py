"""
Web Search Actions - Multiple search providers for AI agents.

This module provides web search capabilities through multiple providers:
1. Perplexity AI (Premium - best for security research)
2. Tavily AI (Good for general search with API)
3. SerpAPI (Google search results via API)
4. DuckDuckGo (Free, no API key required)
5. Google Custom Search API
6. Brave Search API

The module automatically selects the best available provider based on
configured API keys, with fallback to free providers.
"""

import logging
import os
import re
from typing import Any
from urllib.parse import quote_plus

import requests

from strix.tools.registry import register_tool


logger = logging.getLogger(__name__)

# System prompt for security-focused search
SECURITY_SYSTEM_PROMPT = """You are assisting a cybersecurity agent specialized in vulnerability scanning
and security assessment running on Kali Linux. When responding to search queries:

1. Prioritize cybersecurity-relevant information including:
   - Vulnerability details (CVEs, CVSS scores, impact)
   - Security tools, techniques, and methodologies
   - Exploit information and proof-of-concepts
   - Security best practices and mitigations
   - Penetration testing approaches
   - Web application security findings

2. Provide technical depth appropriate for security professionals
3. Include specific versions, configurations, and technical details when available
4. Focus on actionable intelligence for security assessment
5. Cite reliable security sources (NIST, OWASP, CVE databases, security vendors)
6. When providing commands or installation instructions, prioritize Kali Linux compatibility
   and use apt package manager or tools pre-installed in Kali
7. Be detailed and specific - avoid general answers. Always include concrete code examples,
   command-line instructions, configuration snippets, or practical implementation steps
   when applicable

Structure your response to be comprehensive yet concise, emphasizing the most critical
security implications and details."""


def _get_available_providers() -> list[str]:
    """Get list of available search providers based on configured API keys."""
    providers = []
    
    if os.getenv("PERPLEXITY_API_KEY"):
        providers.append("perplexity")
    if os.getenv("TAVILY_API_KEY"):
        providers.append("tavily")
    if os.getenv("SERPAPI_API_KEY"):
        providers.append("serpapi")
    if os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_ID"):
        providers.append("google_cse")
    if os.getenv("BRAVE_API_KEY"):
        providers.append("brave")
    
    # DuckDuckGo is always available (no API key required)
    providers.append("duckduckgo")
    
    return providers


def _search_perplexity(query: str) -> dict[str, Any]:
    """Search using Perplexity AI API."""
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {"success": False, "error": "PERPLEXITY_API_KEY not set"}
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "sonar-reasoning",
            "messages": [
                {"role": "system", "content": SECURITY_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        return {
            "success": True,
            "provider": "perplexity",
            "query": query,
            "content": content,
            "message": "Search completed via Perplexity AI",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Perplexity API error: {e!s}"}
    except (KeyError, IndexError) as e:
        return {"success": False, "error": f"Unexpected response format: {e!s}"}


def _search_tavily(query: str, search_depth: str = "advanced") -> dict[str, Any]:
    """Search using Tavily AI API."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"success": False, "error": "TAVILY_API_KEY not set"}
    
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
            "max_results": 10,
            "include_domains": [
                "exploit-db.com",
                "cvedetails.com",
                "nvd.nist.gov",
                "owasp.org",
                "hackerone.com",
                "portswigger.net",
                "github.com",
                "stackoverflow.com",
            ],
        }
        
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        # Format results
        results = []
        for result in data.get("results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("content", "")[:500],
                "score": result.get("score", 0),
            })
        
        content = data.get("answer", "")
        if not content and results:
            # Compile results into content
            content = "Search Results:\n\n"
            for i, r in enumerate(results[:5], 1):
                content += f"{i}. **{r['title']}**\n"
                content += f"   URL: {r['url']}\n"
                content += f"   {r['snippet']}\n\n"
        
        return {
            "success": True,
            "provider": "tavily",
            "query": query,
            "content": content,
            "results": results,
            "message": "Search completed via Tavily AI",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Tavily API error: {e!s}"}


def _search_serpapi(query: str) -> dict[str, Any]:
    """Search using SerpAPI (Google Search results)."""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"success": False, "error": "SERPAPI_API_KEY not set"}
    
    try:
        url = "https://serpapi.com/search"
        params = {
            "api_key": api_key,
            "q": query,
            "engine": "google",
            "num": 10,
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        for result in data.get("organic_results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
            })
        
        # Compile content
        content = "Search Results:\n\n"
        for i, r in enumerate(results[:7], 1):
            content += f"{i}. **{r['title']}**\n"
            content += f"   URL: {r['url']}\n"
            content += f"   {r['snippet']}\n\n"
        
        # Add answer box if available
        if "answer_box" in data:
            answer = data["answer_box"]
            if "answer" in answer:
                content = f"**Quick Answer:** {answer['answer']}\n\n{content}"
            elif "snippet" in answer:
                content = f"**Featured:** {answer['snippet']}\n\n{content}"
        
        return {
            "success": True,
            "provider": "serpapi",
            "query": query,
            "content": content,
            "results": results,
            "message": "Search completed via SerpAPI (Google)",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"SerpAPI error: {e!s}"}


def _search_google_cse(query: str) -> dict[str, Any]:
    """Search using Google Custom Search Engine API."""
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        return {"success": False, "error": "GOOGLE_CSE_API_KEY or GOOGLE_CSE_ID not set"}
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": 10,
        }
        
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
            })
        
        # Compile content
        content = "Search Results:\n\n"
        for i, r in enumerate(results[:7], 1):
            content += f"{i}. **{r['title']}**\n"
            content += f"   URL: {r['url']}\n"
            content += f"   {r['snippet']}\n\n"
        
        return {
            "success": True,
            "provider": "google_cse",
            "query": query,
            "content": content,
            "results": results,
            "message": "Search completed via Google Custom Search",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Google CSE error: {e!s}"}


def _search_brave(query: str) -> dict[str, Any]:
    """Search using Brave Search API."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        return {"success": False, "error": "BRAVE_API_KEY not set"}
    
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        params = {
            "q": query,
            "count": 10,
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        for result in data.get("web", {}).get("results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("description", ""),
            })
        
        # Compile content
        content = "Search Results:\n\n"
        for i, r in enumerate(results[:7], 1):
            content += f"{i}. **{r['title']}**\n"
            content += f"   URL: {r['url']}\n"
            content += f"   {r['snippet']}\n\n"
        
        return {
            "success": True,
            "provider": "brave",
            "query": query,
            "content": content,
            "results": results,
            "message": "Search completed via Brave Search",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Brave Search error: {e!s}"}


def _search_duckduckgo(query: str) -> dict[str, Any]:
    """Search using DuckDuckGo (free, no API key required)."""
    try:
        # DuckDuckGo Instant Answer API
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        results = []
        content_parts = []
        
        # Abstract (main result)
        if data.get("Abstract"):
            content_parts.append(f"**Summary:** {data['Abstract']}")
            if data.get("AbstractURL"):
                content_parts.append(f"Source: {data['AbstractURL']}")
        
        # Related topics
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })
        
        # Infobox
        if data.get("Infobox"):
            infobox = data["Infobox"]
            if "content" in infobox:
                for item in infobox["content"][:5]:
                    content_parts.append(f"- {item.get('label', '')}: {item.get('value', '')}")
        
        # If no results from instant answer, try HTML scraping as fallback
        if not content_parts and not results:
            # Use DuckDuckGo HTML search
            html_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            html_response = requests.get(html_url, headers=headers, timeout=30)
            html_response.raise_for_status()
            
            # Simple HTML parsing for results
            html = html_response.text
            
            # Extract result blocks using regex
            result_pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
            snippet_pattern = r'<a class="result__snippet"[^>]*>([^<]+)</a>'
            
            urls = re.findall(result_pattern, html)
            snippets = re.findall(snippet_pattern, html)
            
            for i, (url, title) in enumerate(urls[:7]):
                snippet = snippets[i] if i < len(snippets) else ""
                results.append({
                    "title": title.strip(),
                    "url": url,
                    "snippet": snippet.strip(),
                })
                content_parts.append(f"{i+1}. **{title.strip()}**")
                content_parts.append(f"   URL: {url}")
                if snippet:
                    content_parts.append(f"   {snippet.strip()}")
                content_parts.append("")
        
        content = "\n".join(content_parts) if content_parts else "No results found."
        
        if results:
            if not content_parts:
                content = "Search Results:\n\n"
                for i, r in enumerate(results[:7], 1):
                    content += f"{i}. **{r['title']}**\n"
                    content += f"   URL: {r['url']}\n"
                    if r['snippet']:
                        content += f"   {r['snippet']}\n"
                    content += "\n"
        
        return {
            "success": True,
            "provider": "duckduckgo",
            "query": query,
            "content": content,
            "results": results,
            "message": "Search completed via DuckDuckGo (free)",
        }
        
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"DuckDuckGo error: {e!s}"}


@register_tool(sandbox_execution=False)
def web_search(
    query: str,
    provider: str | None = None,
) -> dict[str, Any]:
    """
    Search the web for information relevant to security testing.
    
    This tool supports multiple search providers with automatic fallback:
    1. Perplexity AI (best for security research, requires PERPLEXITY_API_KEY)
    2. Tavily AI (good for general search, requires TAVILY_API_KEY)
    3. SerpAPI (Google results, requires SERPAPI_API_KEY)
    4. Google Custom Search (requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID)
    5. Brave Search (requires BRAVE_API_KEY)
    6. DuckDuckGo (free, always available, no API key needed)
    
    Args:
        query: The search query
        provider: Optional specific provider to use. If not specified,
                  uses the best available provider based on configured API keys.
    
    Returns:
        Dictionary with search results including:
        - success: Whether the search succeeded
        - provider: Which provider was used
        - query: The original query
        - content: Formatted search results/answer
        - results: List of result objects (if available)
        - message: Status message
    """
    available = _get_available_providers()
    
    if not available:
        return {
            "success": False,
            "error": "No search providers available",
            "available_providers": [],
        }
    
    # Provider selection
    if provider:
        if provider not in available:
            return {
                "success": False,
                "error": f"Provider '{provider}' not available. Available: {', '.join(available)}",
                "available_providers": available,
            }
        selected_provider = provider
    else:
        # Auto-select best available provider
        # Priority: perplexity > tavily > serpapi > google_cse > brave > duckduckgo
        priority = ["perplexity", "tavily", "serpapi", "google_cse", "brave", "duckduckgo"]
        selected_provider = next((p for p in priority if p in available), "duckduckgo")
    
    # Execute search with selected provider
    provider_functions = {
        "perplexity": _search_perplexity,
        "tavily": _search_tavily,
        "serpapi": _search_serpapi,
        "google_cse": _search_google_cse,
        "brave": _search_brave,
        "duckduckgo": _search_duckduckgo,
    }
    
    result = provider_functions[selected_provider](query)
    
    # If primary provider fails, try fallbacks
    if not result.get("success") and selected_provider != "duckduckgo":
        logger.warning(f"Primary provider {selected_provider} failed, falling back to DuckDuckGo")
        result = _search_duckduckgo(query)
        if result.get("success"):
            result["fallback_from"] = selected_provider
    
    result["available_providers"] = available
    return result


@register_tool(sandbox_execution=False)
def list_search_providers() -> dict[str, Any]:
    """
    List all available web search providers and their status.
    
    Returns:
        Dictionary with provider information:
        - available: List of providers that can be used
        - unavailable: List of providers that need API keys
        - recommended: The recommended provider to use
    """
    all_providers = {
        "perplexity": {
            "name": "Perplexity AI",
            "env_var": "PERPLEXITY_API_KEY",
            "description": "Best for security research with AI-powered answers",
            "quality": "excellent",
            "cost": "paid",
        },
        "tavily": {
            "name": "Tavily AI",
            "env_var": "TAVILY_API_KEY",
            "description": "Good for general search with structured results",
            "quality": "very good",
            "cost": "freemium",
        },
        "serpapi": {
            "name": "SerpAPI",
            "env_var": "SERPAPI_API_KEY",
            "description": "Google search results via API",
            "quality": "very good",
            "cost": "paid",
        },
        "google_cse": {
            "name": "Google Custom Search",
            "env_var": "GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID",
            "description": "Official Google search API",
            "quality": "very good",
            "cost": "freemium",
        },
        "brave": {
            "name": "Brave Search",
            "env_var": "BRAVE_API_KEY",
            "description": "Privacy-focused search engine",
            "quality": "good",
            "cost": "freemium",
        },
        "duckduckgo": {
            "name": "DuckDuckGo",
            "env_var": "None (free)",
            "description": "Free, privacy-focused, always available",
            "quality": "basic",
            "cost": "free",
        },
    }
    
    available = []
    unavailable = []
    
    for provider_id, info in all_providers.items():
        provider_info = {
            "id": provider_id,
            **info,
        }
        
        if provider_id == "duckduckgo":
            provider_info["status"] = "available"
            available.append(provider_info)
        elif provider_id == "google_cse":
            if os.getenv("GOOGLE_CSE_API_KEY") and os.getenv("GOOGLE_CSE_ID"):
                provider_info["status"] = "available"
                available.append(provider_info)
            else:
                provider_info["status"] = "needs_api_key"
                unavailable.append(provider_info)
        else:
            env_var = info["env_var"]
            if os.getenv(env_var):
                provider_info["status"] = "available"
                available.append(provider_info)
            else:
                provider_info["status"] = "needs_api_key"
                unavailable.append(provider_info)
    
    # Determine recommended provider
    priority = ["perplexity", "tavily", "serpapi", "google_cse", "brave", "duckduckgo"]
    recommended = next(
        (p for p in priority if any(a["id"] == p for a in available)),
        "duckduckgo"
    )
    
    return {
        "success": True,
        "available": available,
        "unavailable": unavailable,
        "recommended": recommended,
        "total_available": len(available),
        "total_unavailable": len(unavailable),
    }
