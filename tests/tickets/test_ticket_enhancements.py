"""
Tests for ticket runner enhancements: ticket_code and branch_template.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from codex_autorunner.tickets.models import TicketRunConfig, BitbucketConfig


class TestTicketRunConfig:
    """Test TicketRunConfig with new fields."""

    def test_config_with_branch_template(self):
        """Test config with branch_template field."""
        config = TicketRunConfig(
            checkpoint_message_template="[DONE][{ticket_code}] {message}",
            branch_template="helios/{ticket_code}-{title_slug}",
        )
        assert config.branch_template == "helios/{ticket_code}-{title_slug}"

    def test_config_without_branch_template(self):
        """Test config without branch_template field."""
        config = TicketRunConfig(
            checkpoint_message_template="[DONE] {message}",
        )
        assert config.branch_template is None

    def test_config_with_bitbucket(self):
        """Test config with Bitbucket config."""
        bitbucket = BitbucketConfig(
            enabled=True,
            access_token="test-token",
            default_reviewers=["user1"],
            close_source_branch=True,
        )
        config = TicketRunConfig(
            checkpoint_message_template="[DONE] {message}",
            bitbucket=bitbucket,
        )
        assert config.bitbucket is not None
        assert config.bitbucket.enabled is True
        assert config.bitbucket.access_token == "test-token"

    def test_config_without_bitbucket(self):
        """Test config without Bitbucket config."""
        config = TicketRunConfig(
            checkpoint_message_template="[DONE] {message}",
        )
        assert config.bitbucket is None


class TestBitbucketConfig:
    """Test BitbucketConfig dataclass."""

    def test_default_values(self):
        """Test default values for Bitbucket config."""
        config = BitbucketConfig()
        assert config.enabled is False
        assert config.access_token == ""
        assert config.default_reviewers == []
        assert config.close_source_branch is True

    def test_custom_values(self):
        """Test custom values for Bitbucket config."""
        config = BitbucketConfig(
            enabled=True,
            access_token="my-token",
            default_reviewers=["user1", "user2"],
            close_source_branch=False,
        )
        assert config.enabled is True
        assert config.access_token == "my-token"
        assert config.default_reviewers == ["user1", "user2"]
        assert config.close_source_branch is False


class TestTicketCodeExtraction:
    """Test ticket_code extraction from path."""

    def test_extract_ticket_code_from_path(self):
        """Test extracting ticket code from path."""
        from codex_autorunner.tickets.runner import TicketRunner

        runner = Mock(spec=TicketRunner)
        runner._extract_ticket_code = (
            lambda path: path.stem
            if hasattr(path, "stem")
            else path.split("/")[-1].replace(".md", "")
        )

        path = Path("tickets/TICKET-001.md")
        result = runner._extract_ticket_code(path)
        assert result == "TICKET-001"

    def test_extract_ticket_code_from_relative_path(self):
        """Test extracting ticket code from relative path."""
        from codex_autorunner.tickets.runner import TicketRunner

        runner = Mock(spec=TicketRunner)
        runner._extract_ticket_code = (
            lambda path: path.stem
            if hasattr(path, "stem")
            else path.split("/")[-1].replace(".md", "")
        )

        path = "tickets/TICKET-042-some-feature.md"
        result = runner._extract_ticket_code(path)
        assert result == "TICKET-042-some-feature"


class TestBranchTemplateNameFormatting:
    """Test branch template name formatting."""

    def test_format_branch_name_with_template(self):
        """Test formatting branch name with template."""
        template = "helios/{ticket_code}-{title_slug}"
        ticket_code = "TICKET-001"
        title = "Add Authentication Feature"

        import re

        title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        branch_name = template.format(ticket_code=ticket_code, title_slug=title_slug)

        assert branch_name == "helios/TICKET-001-add-authentication-feature"

    def test_format_branch_name_with_special_chars(self):
        """Test formatting branch name with special characters in title."""
        template = "helios/{ticket_code}-{title_slug}"
        ticket_code = "TICKET-042"
        title = "Fix: API endpoint /users/{id} bug!"

        import re

        title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        branch_name = template.format(ticket_code=ticket_code, title_slug=title_slug)

        assert "TICKET-042" in branch_name
        assert "/" not in title_slug
        assert "!" not in title_slug

    def test_format_branch_name_short_slug(self):
        """Test formatting branch name with short slug."""
        template = "{ticket_code}-{title_slug}"
        ticket_code = "TICKET-123"
        title = "Fix"

        import re

        title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        branch_name = template.format(ticket_code=ticket_code, title_slug=title_slug)

        assert branch_name == "TICKET-123-fix"


class TestCheckpointMessageTemplate:
    """Test checkpoint message template with ticket_code."""

    def test_template_with_ticket_code(self):
        """Test checkpoint message template with ticket_code variable."""
        template = "[DONE][{ticket_code}][{agent}] {message}"
        result = template.format(
            ticket_code="TICKET-001", agent="copilot", message="Implemented feature"
        )
        assert result == "[DONE][TICKET-001][copilot] Implemented feature"

    def test_template_without_ticket_code(self):
        """Test checkpoint message template without ticket_code variable."""
        template = "[DONE][{agent}] {message}"
        result = template.format(agent="copilot", message="Implemented feature")
        assert result == "[DONE][copilot] Implemented feature"

    def test_template_with_turn_number(self):
        """Test checkpoint message template with turn number."""
        template = "[checkpoint][{ticket_code}][turn-{turn}] {message}"
        result = template.format(
            ticket_code="TICKET-001", turn=3, message="Progress update"
        )
        assert result == "[checkpoint][TICKET-001][turn-3] Progress update"
