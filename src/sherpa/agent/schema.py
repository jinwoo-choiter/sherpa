"""Structured review contract shared by every agent adapter.

The agent's job is to produce a `ReviewResult` (a reviewer's map, not a verdict).
The deterministic approve gate (pre-flight-bot) consumes `category_evidence` as
*advisory* signal only and never treats any field here as an approval — approval
authority lives outside the agent. See review-inference spec.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SEVERITIES = ("info", "nit", "concern")


@dataclass(frozen=True)
class Finding:
    """One inline observation, anchored to a file/line range. Not an approval."""

    file: str
    line_start: int
    line_end: int
    severity: str
    body: str

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity {self.severity!r}; expected one of {SEVERITIES}")


@dataclass(frozen=True)
class ReviewResult:
    summary: str
    findings: tuple[Finding, ...] = ()
    category_evidence: dict[str, object] = field(default_factory=dict)
    open_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewTask:
    pr_id: str
    repo_path: Path
    changed_files: tuple[str, ...]
    form_spec: str
    injected_knowledge: str = ""
    knowledge_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Trajectory:
    """Normalized record of what the agent did, for audit (review-inference)."""

    agent_name: str
    model_id: str = ""
    agent_version: str = ""
    files_read: tuple[str, ...] = ()
    commands_run: tuple[str, ...] = ()
    blocked_attempts: tuple[str, ...] = ()
    raw_session_ref: str | None = None


OUTPUT_SCHEMA_INSTRUCTION = (
    "Respond with a SINGLE JSON object and nothing else, matching:\n"
    "{\n"
    '  "summary": "reviewer map: what this PR does, where risk/complexity '
    'concentrates, and where a human should focus",\n'
    '  "findings": [{"file": str, "line_start": int, "line_end": int, '
    '"severity": "info|nit|concern", "body": str}],\n'
    '  "category_evidence": {"changed_files": [str], "notes": str},\n'
    '  "open_questions": [str]\n'
    "}\n"
    "Rules: You DO NOT approve, LGTM, or 'ship it' — you orient a human reviewer. "
    "`severity` is never an approval signal. `category_evidence` is advisory only."
)


def build_prompt(task: ReviewTask) -> str:
    """Task framing + guardrails handed to an agentic adapter.

    The agent reads the changed files in the checkout itself; we inject only the
    team-specific layers it cannot infer from code (form spec + tacit knowledge).
    """
    knowledge = task.injected_knowledge.strip() or "(none — rely on the convention spec)"
    files = "\n".join(f"- {f}" for f in task.changed_files) or "(none listed)"
    return (
        f"# Convention Spec (form: structure, tone, forbidden phrasings)\n\n{task.form_spec}\n\n"
        f"# Team Tacit Knowledge (judgment the code cannot tell you)\n\n{knowledge}\n\n"
        f"# Changed Files In This PR\n\n{files}\n\n"
        f"# Your Task\n"
        f"Read the changed files in this repository checkout, then produce a "
        f"reviewer's map for PR {task.pr_id}. Surface where to focus; never approve.\n\n"
        f"# Output\n{OUTPUT_SCHEMA_INSTRUCTION}\n"
    )


def extract_json_object(text: str) -> dict[str, object]:
    """Best-effort: pull the first top-level JSON object out of an agent's text."""
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in agent output")


def parse_review_result(data: dict[str, object]) -> ReviewResult:
    raw_findings = data.get("findings") or []
    findings = tuple(
        Finding(
            file=str(f.get("file", "")),
            line_start=int(f.get("line_start", 0) or 0),
            line_end=int(f.get("line_end", f.get("line_start", 0)) or 0),
            severity=str(f.get("severity", "info") or "info"),
            body=str(f.get("body", "")),
        )
        for f in raw_findings
        if isinstance(f, dict)
    )
    evidence = data.get("category_evidence")
    return ReviewResult(
        summary=str(data.get("summary", "")).strip(),
        findings=findings,
        category_evidence=dict(evidence) if isinstance(evidence, dict) else {},
        open_questions=tuple(str(q) for q in (data.get("open_questions") or [])),
    )


def result_to_dict(result: ReviewResult) -> dict[str, object]:
    return {
        "summary": result.summary,
        "findings": [
            {
                "file": f.file,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "severity": f.severity,
                "body": f.body,
            }
            for f in result.findings
        ],
        "category_evidence": result.category_evidence,
        "open_questions": list(result.open_questions),
    }
