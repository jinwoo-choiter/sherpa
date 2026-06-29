"""Claude Code adapter (headless, read-only sandbox).

Invocation targets a current Claude Code CLI; verify flags against the installed
version before production (operator concern). Output is coaxed into our schema.
"""

from __future__ import annotations

import json
import subprocess

from sherpa.agent import sandbox
from sherpa.agent.base import AgentError, register
from sherpa.agent.schema import (
    ReviewResult,
    ReviewTask,
    Trajectory,
    build_prompt,
    extract_json_object,
    parse_review_result,
)

NAME = "claude"
_TIMEOUT = 900.0


def _build_argv(model: str | None) -> list[str]:
    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--allowedTools",
        " ".join(sandbox.CLAUDE_ALLOWED_TOOLS),
    ]
    if model:
        argv += ["--model", model]
    return argv


def _parse(stdout: str) -> tuple[ReviewResult, Trajectory]:
    text, model, session = stdout, "", None
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        envelope = None
    if isinstance(envelope, dict):
        text = str(envelope.get("result", stdout))
        model = str(envelope.get("model", ""))
        sid = envelope.get("session_id")
        session = str(sid) if sid else None
    result = parse_review_result(extract_json_object(text))
    return result, Trajectory(agent_name=NAME, model_id=model, raw_session_ref=session)


class ClaudeAgent:
    name = NAME

    def __init__(self, model: str | None = None) -> None:
        self._model = model

    def review(self, task: ReviewTask) -> tuple[ReviewResult, Trajectory]:
        prompt = build_prompt(task)
        try:
            proc = subprocess.run(
                _build_argv(self._model),
                input=prompt,
                cwd=str(task.repo_path),
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AgentError(f"claude invocation failed: {exc}") from exc
        if proc.returncode != 0:
            raise AgentError(f"claude exited {proc.returncode}: {proc.stderr[:300]}")
        try:
            return _parse(proc.stdout)
        except ValueError as exc:
            raise AgentError(f"could not parse claude output: {exc}") from exc


register(NAME, ClaudeAgent)
