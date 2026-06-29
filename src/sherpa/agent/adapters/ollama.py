"""Legacy Ollama adapter (non-agentic, summary-only fallback).

Ollama is a text endpoint, not an agent: it cannot explore a repo on its own.
This adapter honors the ReviewAgent contract by reading the changed files itself
(capped) and asking for a summary. It returns no inline findings — that is the
known limitation of the local-only fallback path. The `_assert_local` guard in
`inference/llm.py` still applies here.
"""

from __future__ import annotations

import os

from sherpa.agent.base import AgentError, register
from sherpa.agent.schema import (
    ReviewResult,
    ReviewTask,
    Trajectory,
    build_prompt,
    extract_json_object,
    parse_review_result,
)
from sherpa.inference.llm import LLMClient

NAME = "ollama"
_DEFAULT_BASE = "http://127.0.0.1:11434"
_DEFAULT_MODEL = "qwen2.5-coder:32b-instruct-q4_K_M"
_PER_FILE_CAP = 4000


def _read_changed_files(task: ReviewTask) -> str:
    blocks = []
    for rel in task.changed_files:
        path = task.repo_path / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:_PER_FILE_CAP]
        except OSError:
            continue
        blocks.append(f"--- {rel}\n{text}")
    return "\n\n".join(blocks)


class OllamaAgent:
    name = NAME

    def review(self, task: ReviewTask) -> tuple[ReviewResult, Trajectory]:
        base = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_BASE)
        model = os.environ.get("SHERPA_LLM_MODEL", _DEFAULT_MODEL)
        prompt = build_prompt(task) + "\n\n# File Contents\n\n" + _read_changed_files(task)
        try:
            with LLMClient(base, model) as llm:
                raw = llm.generate(prompt)
        except Exception as exc:  # network/runtime — surface as an agent error
            raise AgentError(f"ollama generate failed: {exc}") from exc
        try:
            result = parse_review_result(extract_json_object(raw))
        except ValueError:
            result = ReviewResult(summary=raw.strip())
        return result, Trajectory(agent_name=NAME, model_id=model)


register(NAME, OllamaAgent)
