# Issue #208

Issue #208 (Telegram: Opencode streaming work becomes unresponsive on tool (subagent) calls) has been resolved by PR #213.

## Implementation Details

All requirements from issue #208 were implemented in commit 9bf9d2539f1253abed0564e4b576fd34335ff360:

### 1. Multiple Session Watching
- Added `progress_session_ids` parameter to OpenCode runtime collectors
- Events filtered by session ID to watch parent and subagent sessions
- Text accumulation restricted to primary session only
- Permission handling extended to all watched sessions
- Child session errors don't break parent collector

### 2. Inline Subagent Progress
- Session-scoped item IDs prevent ID collisions
- Subagent labels extracted from task tool's subagent_type
- Reasoning deltas for subagents displayed with labels
- Tool status updates for subagents rendered with proper labels

### 3. Progress Heartbeat
- 5-second heartbeat interval (PROGRESS_HEARTBEAT_INTERVAL_SECONDS)
- Background task updates progress timer even when events stop
- Proper cleanup on turn completion and cache eviction

This documentation file exists to provide reference for future maintenance of the subagent progress streaming feature.
