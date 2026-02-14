"""
Tests for Bitbucket PR integration.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from codex_autorunner.integrations.bitbucket.client import BitbucketClient
from codex_autorunner.integrations.bitbucket.pr import (
    PullRequestResult,
    create_pull_request,
    get_workspace_from_git_url,
    get_repo_slug_from_git_url,
    slugify,
)


class TestBitbucketClient:
    """Test BitbucketClient class."""

    def test_init_with_token(self):
        """Test client initialization with access token."""
        client = BitbucketClient(access_token="test-token")
        assert client.access_token == "test-token"
        assert client.base_url == "https://api.bitbucket.org/2.0"

    def test_init_with_custom_url(self):
        """Test client initialization with custom base URL."""
        client = BitbucketClient(
            access_token="test-token", base_url="https://custom.bitbucket.com/api"
        )
        assert client.base_url == "https://custom.bitbucket.com/api"

    @patch("codex_autorunner.integrations.bitbucket.client.requests.post")
    def test_create_pull_request_success(self, mock_post):
        """Test successful PR creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 1,
            "title": "Test PR",
            "links": {
                "html": {"href": "https://bitbucket.org/test/test-repo/pull-requests/1"}
            },
        }
        mock_post.return_value = mock_response

        client = BitbucketClient(access_token="test-token")
        result = client.create_pull_request(
            workspace="test-workspace",
            repo_slug="test-repo",
            title="Test PR",
            description="Test description",
            source_branch="feature-branch",
            dest_branch="main",
        )

        assert result["id"] == 1
        assert result["title"] == "Test PR"
        mock_post.assert_called_once()

    @patch("codex_autorunner.integrations.bitbucket.client.requests.post")
    def test_create_pull_request_with_reviewers(self, mock_post):
        """Test PR creation with reviewers."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 1,
            "title": "Test PR",
            "links": {
                "html": {"href": "https://bitbucket.org/test/test-repo/pull-requests/1"}
            },
        }
        mock_post.return_value = mock_response

        client = BitbucketClient(access_token="test-token")
        result = client.create_pull_request(
            workspace="test-workspace",
            repo_slug="test-repo",
            title="Test PR",
            description="Test description",
            source_branch="feature-branch",
            dest_branch="main",
            reviewers=["user1", "user2"],
        )

        assert result["id"] == 1
        call_args = mock_post.call_args
        request_body = call_args.kwargs["json"]
        assert len(request_body["reviewers"]) == 2

    @patch("codex_autorunner.integrations.bitbucket.client.requests.post")
    def test_create_pull_request_error(self, mock_post):
        """Test PR creation error handling."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        client = BitbucketClient(access_token="test-token")
        with pytest.raises(Exception) as exc_info:
            client.create_pull_request(
                workspace="test-workspace",
                repo_slug="test-repo",
                title="Test PR",
                description="Test description",
                source_branch="feature-branch",
                dest_branch="main",
            )
        assert "400" in str(exc_info.value)


class TestPullRequestResult:
    """Test PullRequestResult dataclass."""

    def test_success_result(self):
        """Test successful PR result."""
        result = PullRequestResult(
            success=True,
            pr_id=1,
            pr_url="https://bitbucket.org/test/test-repo/pull-requests/1",
            message="PR created successfully",
        )
        assert result.success is True
        assert result.pr_id == 1
        assert result.pr_url == "https://bitbucket.org/test/test-repo/pull-requests/1"

    def test_failure_result(self):
        """Test failed PR result."""
        result = PullRequestResult(
            success=False,
            pr_id=None,
            pr_url=None,
            message="Failed to create PR",
        )
        assert result.success is False
        assert result.pr_id is None
        assert result.pr_url is None


class TestUrlParsing:
    """Test URL parsing functions."""

    def test_get_workspace_from_https_url(self):
        """Test extracting workspace from HTTPS URL."""
        url = "https://bitbucket.org/my-workspace/my-repo.git"
        assert get_workspace_from_git_url(url) == "my-workspace"

    def test_get_workspace_from_ssh_url(self):
        """Test extracting workspace from SSH URL."""
        url = "git@bitbucket.org:my-workspace/my-repo.git"
        assert get_workspace_from_git_url(url) == "my-workspace"

    def test_get_repo_slug_from_https_url(self):
        """Test extracting repo slug from HTTPS URL."""
        url = "https://bitbucket.org/my-workspace/my-repo.git"
        assert get_repo_slug_from_git_url(url) == "my-repo"

    def test_get_repo_slug_from_ssh_url(self):
        """Test extracting repo slug from SSH URL."""
        url = "git@bitbucket.org:my-workspace/my-repo.git"
        assert get_repo_slug_from_git_url(url) == "my-repo"

    def test_get_repo_slug_without_git_suffix(self):
        """Test extracting repo slug without .git suffix."""
        url = "https://bitbucket.org/my-workspace/my-repo"
        assert get_repo_slug_from_git_url(url) == "my-repo"


class TestSlugify:
    """Test slugify function."""

    def test_simple_string(self):
        """Test slugifying a simple string."""
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        """Test slugifying string with special characters."""
        assert slugify("Hello!@#$%World") == "hello-world"

    def test_multiple_spaces(self):
        """Test slugifying string with multiple spaces."""
        assert slugify("Hello    World") == "hello-world"

    def test_empty_string(self):
        """Test slugifying empty string."""
        assert slugify("") == ""

    def test_unicode_characters(self):
        """Test slugifying string with unicode characters."""
        result = slugify("Hello World")
        assert result == "hello-world"


class TestCreatePullRequest:
    """Test create_pull_request function."""

    @patch("codex_autorunner.integrations.bitbucket.pr.get_git_remote_url")
    @patch("codex_autorunner.integrations.bitbucket.pr.BitbucketClient")
    def test_create_pull_request_success(self, mock_client_class, mock_get_remote):
        """Test successful PR creation via helper function."""
        mock_get_remote.return_value = (
            "https://bitbucket.org/test-workspace/test-repo.git"
        )
        mock_client = Mock()
        mock_client.create_pull_request.return_value = {
            "id": 1,
            "links": {
                "html": {"href": "https://bitbucket.org/test/test-repo/pull-requests/1"}
            },
        }
        mock_client_class.return_value = mock_client

        result = create_pull_request(
            access_token="test-token",
            title="Test PR",
            description="Test description",
            source_branch="feature-branch",
        )

        assert result.success is True
        assert result.pr_id == 1
        mock_client.create_pull_request.assert_called_once()

    @patch("codex_autorunner.integrations.bitbucket.pr.get_git_remote_url")
    def test_create_pull_request_no_remote(self, mock_get_remote):
        """Test PR creation when no remote URL is found."""
        mock_get_remote.return_value = None

        result = create_pull_request(
            access_token="test-token",
            title="Test PR",
            description="Test description",
            source_branch="feature-branch",
        )

        assert result.success is False
        assert "No remote URL" in result.message

    @patch("codex_autorunner.integrations.bitbucket.pr.get_git_remote_url")
    @patch("codex_autorunner.integrations.bitbucket.pr.BitbucketClient")
    def test_create_pull_request_with_reviewers(
        self, mock_client_class, mock_get_remote
    ):
        """Test PR creation with default reviewers."""
        mock_get_remote.return_value = (
            "https://bitbucket.org/test-workspace/test-repo.git"
        )
        mock_client = Mock()
        mock_client.create_pull_request.return_value = {
            "id": 1,
            "links": {
                "html": {"href": "https://bitbucket.org/test/test-repo/pull-requests/1"}
            },
        }
        mock_client_class.return_value = mock_client

        result = create_pull_request(
            access_token="test-token",
            title="Test PR",
            description="Test description",
            source_branch="feature-branch",
            default_reviewers=["user1", "user2"],
        )

        assert result.success is True
        call_args = mock_client.create_pull_request.call_args
        assert call_args.kwargs["reviewers"] == ["user1", "user2"]
