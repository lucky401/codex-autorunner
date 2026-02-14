"""Bitbucket API client."""

import os
from typing import Any, Optional

import httpx


class BitbucketClient:
    """Bitbucket API client for repository operations."""

    API_BASE = "https://api.bitbucket.org/2.0"

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Bitbucket client.

        Args:
            access_token: Bitbucket access token. If not provided, will look for
                          BITBUCKET_ACCESS_TOKEN environment variable.
        """
        self.access_token = access_token or os.environ.get("BITBUCKET_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError(
                "Bitbucket access token required. Set BITBUCKET_ACCESS_TOKEN "
                "environment variable or pass access_token parameter."
            )

        self.client = httpx.Client(
            base_url=self.API_BASE,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.client.close()

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for httpx

        Returns:
            Response JSON data

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        response = self.client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_repository(self, workspace: str, repo_slug: str) -> dict[str, Any]:
        """
        Get repository information.

        Args:
            workspace: Bitbucket workspace (organization)
            repo_slug: Repository slug (identifier)

        Returns:
            Repository data
        """
        return self._request("GET", f"/repositories/{workspace}/{repo_slug}")

    def get_default_reviewers(
        self, workspace: str, repo_slug: str
    ) -> list[dict[str, Any]]:
        """
        Get default reviewers for a repository.

        Args:
            workspace: Bitbucket workspace
            repo_slug: Repository slug

        Returns:
            List of default reviewers
        """
        try:
            data = self._request(
                "GET", f"/repositories/{workspace}/{repo_slug}/default-reviewers"
            )
            return data.get("values", [])
        except httpx.HTTPStatusError:
            return []
