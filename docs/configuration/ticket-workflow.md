# Ticket Workflow Configuration

This document covers configuration options for the ticket-based workflow, including commit templates, branch naming, and PR integration.

## Template Variables

### Commit Message Template

The `git.commit_message_template` config option supports the following variables:

| Variable | Description |
|----------|-------------|
| `{run_id}` | The unique run identifier |
| `{turn}` | The current turn number |
| `{agent}` | The agent name |
| `{ticket_code}` | The ticket code (e.g., `TICKET-001`) |

Example configuration:

```yaml
git:
  commit_message_template: "[DONE][{ticket_code}][{agent}] checkpoint turn {turn}"
```

This produces commit messages like:
```
[DONE][TICKET-001][opencode] checkpoint turn 3
```

### Branch Template

The `ticket_flow.branch_template` config option controls automatic branch creation when a new ticket is started.

| Variable | Description |
|----------|-------------|
| `{ticket_code}` | The ticket code (e.g., `TICKET-001`) |
| `{title_slug}` | The ticket title converted to a URL-safe slug |

Example configuration:

```yaml
ticket_flow:
  branch_template: "helios/{ticket_code}-{title_slug}"
```

For a ticket titled "Add authentication" with code `TICKET-001`, this creates:
```
helios/TICKET-001-add-authentication
```

## Bitbucket Integration

CAR can automatically create pull requests in Bitbucket after a ticket is completed.

### Configuration

```yaml
bitbucket:
  enabled: true
  access_token: ""  # Or use env: BITBUCKET_ACCESS_TOKEN
  default_reviewers: []
  close_source_branch: true
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `BITBUCKET_ACCESS_TOKEN` | Bitbucket API access token |

### How It Works

1. When a ticket is marked as `done: true`, CAR checks if Bitbucket integration is enabled
2. CAR creates a pull request from the current branch to the default branch
3. The PR URL is stored in the ticket frontmatter

### Ticket Frontmatter

After PR creation, the ticket frontmatter is updated:

```yaml
---
title: "Add authentication"
done: true
pr_url: "https://bitbucket.org/workspace/repo/pull-requests/123"
---
```

## Complete Example

```yaml
# codex-autorunner.yml

git:
  commit_message_template: "[DONE][{ticket_code}][{agent}] {message}"

ticket_flow:
  branch_template: "helios/{ticket_code}-{title_slug}"

bitbucket:
  enabled: true
  access_token: "env:BITBUCKET_ACCESS_TOKEN"
  default_reviewers:
    - "username1"
    - "username2"
  close_source_branch: true
```

## Disabling Features

To disable automatic branch creation:

```yaml
ticket_flow:
  branch_template: null  # or omit this key
```

To disable Bitbucket PR creation:

```yaml
bitbucket:
  enabled: false
```
