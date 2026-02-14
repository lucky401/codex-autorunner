"""Bitbucket Pull Request operations."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from .client import BitbucketClient

logger = logging.getLogger(__name__)


@dataclass
class PullRequestResult:
    """Result of a pull request creation."""

    success: bool
    pr_id: Optional[int] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None


def get_workspace_from_git_url(git_url: str) -> Optional[str]:
    """
    Extract workspace from a Bitbucket git URL.

    Supports formats:
    - git@bitbucket.org:workspace/repo.git
    - https://bitbucket.org/workspace/repo.git

    Args:
        git_url: Git remote URL

    Returns:
        Workspace name or None if not found
    """
    patterns = [
        r"git@bitbucket\.org:([^/]+)/",
        r"https://bitbucket\.org/([^/]+)/",
        r"ssh://git@bitbucket\.org/([^/]+)/",
    ]

    for pattern in patterns:
        match = re.search(pattern, git_url)
        if match:
            return match.group(1)

    return None


def get_repo_slug_from_git_url(git_url: str) -> Optional[str]:
    """
    Extract repository slug from a Bitbucket git URL.

    Supports formats:
    - git@bitbucket.org:workspace/repo.git
    - https://bitbucket.org/workspace/repo.git

    Args:
        git_url: Git remote URL

    Returns:
        Repository slug or None if not found
    """
    patterns = [
        r"bitbucket\.org[:/]([^/]+)/([^/.]+)(?:\.git)?",
    ]

    for pattern in patterns:
        match = re.search(pattern, git_url)
        if match:
            return match.group(2)

    return None


class BitbucketPRClient:
    """Client for creating and managing Bitbucket pull requests."""

    def __init__(self, client: Optional[BitbucketClient] = None):
        """
        Initialize PR client.

        Args:
            client: BitbucketClient instance. If not provided, will create one.
        """
        self._owns_client = client is None
        self.client = client or BitbucketClient()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._owns_client:
            self.client.close()

    def close(self):
        """Close the client if we own it."""
        if self._owns_client:
            self.client.close()

    def create_pull_request(
        self,
        workspace: str,
        repo_slug: str,
        title: str,
        description: str,
        source_branch: str,
        dest_branch: str = "main",
        reviewers: Optional[list[str]] = None,
        close_source_branch: bool = True,
    ) -> PullRequestResult:
        """
        Create a pull request in Bitbucket.

        Args:
            workspace: Bitbucket workspace
            repo_slug: Repository slug
            title: PR title
            description: PR description
            source_branch: Source branch name
            dest_branch: Destination branch name (default: main)
            reviewers: List of reviewer UUIDs or usernames
            close_source_branch: Whether to close source branch after merge

        Returns:
            PullRequestResult with PR details or error
        """
        try:
            payload = {
                "title": title,
                "description": description,
                "source": {
                    "branch": {
                        "name": source_branch,
                    },
                },
                "destination": {
                    "branch": {
                        "name": dest_branch,
                    },
                },
                "close_source_branch": close_source_branch,
            }

            if reviewers:
                payload["reviewers"] = [
                    {"uuid": r} if r.startswith("{") else {"username": r}
                    for r in reviewers
                ]

            response = self.client._request(
                "POST",
                f"/repositories/{workspace}/{repo_slug}/pullrequests",
                json=payload,
            )

            pr_id = response.get("id")
            pr_url = response.get("links", {}).get("html", {}).get("href")

            logger.info(f"Created PR #{pr_id}: {pr_url}")

            return PullRequestResult(
                success=True,
                pr_id=pr_id,
                pr_url=pr_url,
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to create PR: {error_msg}")
            return PullRequestResult(
                success=False,
                error=error_msg,
            )

    def create_pull_request_from_git_url(
        self,
        git_url: str,
        title: str,
        description: str,
        source_branch: str,
        dest_branch: str = "main",
        reviewers: Optional[list[str]] = None,
        close_source_branch: bool = True,
    ) -> PullRequestResult:
        """
        Create a pull request using git remote URL to identify repository.

        Args:
            git_url: Git remote URL
            title: PR title
            description: PR description
            source_branch: Source branch name
            dest_branch: Destination branch name
            reviewers: List of reviewer UUIDs or usernames
            close_source_branch: Whether to close source branch after merge

        Returns:
            PullRequestResult with PR details or error
        """
        workspace = get_workspace_from_git_url(git_url)
        repo_slug = get_repo_slug_from_git_url(git_url)

        if not workspace or not repo_slug:
            return PullRequestResult(
                success=False,
                error=f"Could not parse workspace/repo from git URL: {git_url}",
            )

        return self.create_pull_request(
            workspace=workspace,
            repo_slug=repo_slug,
            title=title,
            description=description,
            source_branch=source_branch,
            dest_branch=dest_branch,
            reviewers=reviewers,
            close_source_branch=close_source_branch,
        )
