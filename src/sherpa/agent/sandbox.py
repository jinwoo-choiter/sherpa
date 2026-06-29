"""Read-only sandbox policy for agent execution (design D5).

PR content is untrusted: a diff may carry prompt injection trying to subvert the
review or extract secrets. Every adapter runs its agent read-only — no file
mutation, no `git push`, no network beyond the sanctioned model endpoint — and no
agent can perform a merge-affecting action. Approval authority lives outside the
agent (the deterministic gate in pre-flight-bot), so even a fully jailbroken
agent cannot approve.
"""

from __future__ import annotations

# Claude Code: restrict the headless run to read-only tools (no Edit/Write, no
# mutating Bash). Verify tool names against the installed CLI version.
CLAUDE_ALLOWED_TOOLS = ("Read", "Grep", "Glob")

# Codex CLI sandbox mode that forbids writes and network side effects.
CODEX_SANDBOX_MODE = "read-only"
