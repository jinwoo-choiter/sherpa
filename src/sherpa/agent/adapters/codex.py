"""Codex CLI adapter (non-interactive, read-only sandbox).

Invocation targets a current Codex CLI; verify flags against the installed version
before production (operator concern). Output is coaxed into our schema.
"""

from __future__ import annotations

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

NAME = "codex"
_TIMEOUT = 900.0


def _build_argv(model: str | None) -> list[str]:
    argv = ["codex", "exec", "--sandbox", sandbox.CODEX_SANDBOX_MODE]
    if model:
        argv += ["--model", model]
    return argv


def _parse(stdout: str) -> tuple[ReviewResult, Trajectory]:
    result = parse_review_result(extract_json_object(stdout))
    return result, Trajectory(agent_name=NAME)


class CodexAgent:
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
            raise AgentError(f"codex invocation failed: {exc}") from exc
        if proc.returncode != 0:
            raise AgentError(f"codex exited {proc.returncode}: {proc.stderr[:300]}")
        try:
            return _parse(proc.stdout)
        except ValueError as exc:
            raise AgentError(f"could not parse codex output: {exc}") from exc


register(NAME, CodexAgent)
