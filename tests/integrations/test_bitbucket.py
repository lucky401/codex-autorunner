"""Tests for Bitbucket integration."""

from dataclasses import fields

from codex_autorunner.integrations.bitbucket.client import BitbucketClient
from codex_autorunner.integrations.bitbucket.pr import PullRequestResult


class TestPullRequestResult:
    """Tests for PullRequestResult dataclass."""

    def test_pull_request_result_fields(self):
        """PullRequestResult has expected fields."""
        field_names = {f.name for f in fields(PullRequestResult)}
        assert field_names == {"success", "pr_id", "pr_url", "error"}

    def test_pull_request_result_success(self):
        """PullRequestResult can be created with success=True."""
        result = PullRequestResult(
            success=True, pr_id=123, pr_url="https://example.com/pr/123"
        )
        assert result.success
        assert result.pr_id == 123
        assert result.pr_url == "https://example.com/pr/123"
        assert result.error is None

    def test_pull_request_result_failure(self):
        """PullRequestResult can be created with success=False."""
        result = PullRequestResult(success=False, error="API error")
        assert not result.success
        assert result.pr_id is None
        assert result.pr_url is None
        assert result.error == "API error"


class TestBitbucketClient:
    """Tests for BitbucketClient."""

    def test_api_base_constant(self):
        """BitbucketClient has API_BASE constant."""
        assert BitbucketClient.API_BASE == "https://api.bitbucket.org/2.0"

    def test_has_expected_methods(self):
        """BitbucketClient has expected methods."""
        methods = [
            m
            for m in dir(BitbucketClient)
            if not m.startswith("_") and callable(getattr(BitbucketClient, m))
        ]
        assert "close" in methods
        assert "get_default_reviewers" in methods
        assert "get_repository" in methods
