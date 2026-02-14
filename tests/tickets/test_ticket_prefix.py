"""Tests for configurable ticket prefix functionality."""

from __future__ import annotations

from pathlib import Path

from codex_autorunner.tickets.lint import parse_ticket_index
from codex_autorunner.tickets.models import TicketRunConfig


class TestParseTicketIndexWithPrefix:
    def test_default_prefix_matches_ticket(self) -> None:
        assert parse_ticket_index("TICKET-001.md") == 1
        assert parse_ticket_index("TICKET-123.md") == 123
        assert parse_ticket_index("TICKET-001-some-title.md") == 1

    def test_default_prefix_case_insensitive(self) -> None:
        assert parse_ticket_index("ticket-001.md") == 1
        assert parse_ticket_index("Ticket-123.md") == 123

    def test_default_prefix_rejects_invalid(self) -> None:
        assert parse_ticket_index("TICKET-1.md") is None
        assert parse_ticket_index("TICKET-12.md") is None
        assert parse_ticket_index("TICKET-.md") is None
        assert parse_ticket_index("NOTICKET-001.md") is None

    def test_custom_prefix_qc(self) -> None:
        assert parse_ticket_index("QC-001.md", ticket_prefix="QC") == 1
        assert parse_ticket_index("QC-123.md", ticket_prefix="QC") == 123
        assert parse_ticket_index("QC-001-feature.md", ticket_prefix="QC") == 1
        assert parse_ticket_index("qc-001.md", ticket_prefix="QC") == 1

    def test_custom_prefix_jira(self) -> None:
        assert parse_ticket_index("JIRA-001.md", ticket_prefix="JIRA") == 1
        assert parse_ticket_index("JIRA-999.md", ticket_prefix="JIRA") == 999
        assert parse_ticket_index("JIRA-001-task.md", ticket_prefix="JIRA") == 1

    def test_custom_prefix_rejects_wrong_prefix(self) -> None:
        assert parse_ticket_index("TICKET-001.md", ticket_prefix="QC") is None
        assert parse_ticket_index("QC-001.md", ticket_prefix="JIRA") is None

    def test_custom_prefix_with_special_chars(self) -> None:
        assert parse_ticket_index("PROJ-001.md", ticket_prefix="PROJ") == 1
        assert parse_ticket_index("ABC-XYZ-001.md", ticket_prefix="ABC-XYZ") == 1


class TestTicketRunConfigPrefix:
    def test_default_ticket_prefix(self) -> None:
        cfg = TicketRunConfig(
            ticket_dir=Path(".codex-autorunner/tickets"),
            runs_dir=Path(".codex-autorunner/runs"),
        )
        assert cfg.ticket_prefix == "TICKET"

    def test_custom_ticket_prefix(self) -> None:
        cfg = TicketRunConfig(
            ticket_dir=Path(".codex-autorunner/tickets"),
            runs_dir=Path(".codex-autorunner/runs"),
            ticket_prefix="QC",
        )
        assert cfg.ticket_prefix == "QC"

    def test_jira_prefix(self) -> None:
        cfg = TicketRunConfig(
            ticket_dir=Path(".codex-autorunner/tickets"),
            runs_dir=Path(".codex-autorunner/runs"),
            ticket_prefix="JIRA",
        )
        assert cfg.ticket_prefix == "JIRA"
