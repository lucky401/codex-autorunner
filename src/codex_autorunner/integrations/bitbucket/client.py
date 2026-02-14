"""Bitbucket API client."""

import base64
import os
from typing import Any, Optional

import httpx


class BitbucketClient:
    """Bitbucket API client for repository operations."""

    API_BASE = "https://api.bitbucket.org/2.0"

    def __init__(
        self,
        access_token: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        """
        Initialize Bitbucket client.

        Args:
            access_token: Bitbucket API token. If not provided, will look for
                          BITBUCKET_ACCESS_TOKEN environment variable.
            user_email: Atlassian account email for Basic auth. If not provided,
                        will look for BITBUCKET_USER_EMAIL environment variable.
        """
        self.access_token = access_token or os.environ.get("BITBUCKET_ACCESS_TOKEN")
        self.user_email = user_email or os.environ.get("BITBUCKET_USER_EMAIL")

        if not self.access_token:
            raise ValueError(
                "Bitbucket access token required. Set BITBUCKET_ACCESS_TOKEN "
                "environment variable or pass access_token parameter."
            )

        # Atlassian API tokens require Basic auth with email:token
        if self.user_email:
            credentials = f"{self.user_email}:{self.access_token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            auth_header = f"Basic {encoded}"
        else:
            # Fallback to Bearer for repository access tokens
            auth_header = f"Bearer {self.access_token}"

        self.client = httpx.Client(
            base_url=self.API_BASE,
            headers={
                "Authorization": auth_header,
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
