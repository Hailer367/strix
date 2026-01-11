"""StrixDB client for remote tool server - handles artifact persistence."""

import base64
import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class StrixDBClient:
    """Client for interacting with StrixDB GitHub repository."""

    def __init__(self) -> None:
        """Initialize StrixDB client with token from environment."""
        self.token = os.getenv("STRIXDB_TOKEN", "")
        self.branch = os.getenv("STRIXDB_BRANCH", "main")
        self.repo_name = os.getenv("STRIXDB_REPO", "StrixDB")
        self.owner = self._get_owner_from_token()
        self.api_base = "https://api.github.com"

    def _get_owner_from_token(self) -> str:
        """Get repository owner from GitHub token."""
        if not self.token:
            return ""

        try:
            response = requests.get(
                f"{self.api_base}/user",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("login", "")
        except requests.RequestException as e:
            logger.warning(f"Failed to get owner from token: {e}")

        return ""

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get_repo_path(self) -> str:
        """Get full repository path (owner/repo)."""
        if "/" in self.repo_name:
            return self.repo_name
        return f"{self.owner}/{self.repo_name}" if self.owner else ""

    def save_artifact(
        self,
        category: str,
        name: str,
        content: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save an artifact to StrixDB.

        Args:
            category: Category for the artifact
            name: Name of the artifact
            content: Content to save
            description: Description of the artifact
            tags: List of tags

        Returns:
            Dictionary with operation result
        """
        if not self.token or not self.owner:
            return {
                "success": False,
                "error": "StrixDB not configured. Ensure STRIXDB_TOKEN is set.",
            }

        repo_path = self._get_repo_path()
        if not repo_path:
            return {
                "success": False,
                "error": "Failed to determine repository path",
            }

        # Sanitize category and name
        category = category.lower().replace(" ", "_")
        name = name.replace(" ", "_").replace("/", "_")

        # Create file path
        file_path = f"{category}/{name}.json"

        # Create metadata
        metadata = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "category": category,
            "content": content,
            "created_at": str(os.urandom(8).hex()),  # Simple timestamp placeholder
        }

        try:
            # Check if file exists
            url = f"{self.api_base}/repos/{repo_path}/contents/{file_path}"
            response = requests.get(url, headers=self._get_headers(), timeout=10)

            content_encoded = base64.b64encode(json.dumps(metadata).encode()).decode()
            data: dict[str, Any] = {
                "message": f"Add/update {category}/{name}",
                "content": content_encoded,
                "branch": self.branch,
            }

            if response.status_code == 200:
                # File exists, update it
                data["sha"] = response.json()["sha"]
                data["message"] = f"Update {category}/{name}"

            # Create or update file
            response = requests.put(url, headers=self._get_headers(), json=data, timeout=30)

            if response.status_code in (200, 201):
                return {
                    "success": True,
                    "message": f"Saved {category}/{name} to StrixDB",
                    "path": file_path,
                }

            return {
                "success": False,
                "error": f"Failed to save to StrixDB: {response.status_code}",
            }

        except requests.RequestException as e:
            logger.exception(f"Error saving artifact to StrixDB: {e}")
            return {
                "success": False,
                "error": f"Request error: {str(e)}",
            }

    def is_configured(self) -> bool:
        """Check if StrixDB is properly configured."""
        return bool(self.token and self.owner)
