"""Prompt assembly + post-processing.

Layout (D1, review-inference Spec/RAG split):
- System: spec/SKILL.md content (form rules, tone, forbidden phrasings, domain checklists).
- Exemplars: top-N RAG senior comments (judgment examples).
- Task: current PR diff + instruction to produce a single integrated [pre-flight] comment.

Post-processing enforces:
- Body MUST start with the literal '[pre-flight]' prefix (prepend if missing).
- Approve-style language is stripped; if removal would empty the output, we
  inject a placeholder neutral note rather than letting an approval slip through.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

PREFIX = "[pre-flight]"

APPROVE_PATTERNS = [
    re.compile(r"\bLGTM\b", re.IGNORECASE),
    re.compile(r"\blooks good to me\b", re.IGNORECASE),
    re.compile(r"\bship it\b", re.IGNORECASE),
    re.compile(r"\bapproved?\b", re.IGNORECASE),
    re.compile(r"^\s*✅\s*$", re.MULTILINE),
    re.compile(r"승인합니다"),
    re.compile(r"머지하셔도\s*됩니다"),
]

DEFAULT_SYSTEM_FALLBACK = (
    "You are a pre-flight code reviewer for the team. You DO NOT approve PRs. "
    "Surface only surface-level convention issues, common missed cases, and "
    "domain-specific hazards. Use a neutral, non-prescriptive tone. The human "
    "reviewer makes the actual call."
)


@dataclass(frozen=True)
class Exemplar:
    comment_id: str
    pr_url: str
    role: str
    body: str
    diff_excerpt: str


@dataclass(frozen=True)
class AssembledPrompt:
    text: str
    spec_version_hash: str
    exemplar_ids: tuple[str, ...]


def assemble(
    *,
    skill_md_path: Path | None,
    exemplars: Sequence[Exemplar],
    pr_diff: str,
) -> AssembledPrompt:
    spec_text, spec_hash = _load_spec(skill_md_path)
    exemplar_text = _render_exemplars(exemplars)

    body = (
        f"# Convention Spec\n\n{spec_text}\n\n"
        f"# Past Senior Examples (judgment only — do NOT copy phrasing)\n\n{exemplar_text}\n\n"
        f"# Current PR Diff\n\n```diff\n{pr_diff}\n```\n\n"
        f"# Output Instructions\n"
        f"Write ONE integrated pre-flight note for the entire PR. Begin with the literal "
        f"prefix `{PREFIX}`. Do NOT approve, LGTM, or 'ship it'. Surface only convention "
        f"issues, hazards, and missed cases worth a human reviewer's attention.\n"
    )
    return AssembledPrompt(
        text=body,
        spec_version_hash=spec_hash,
        exemplar_ids=tuple(e.comment_id for e in exemplars),
    )


def _load_spec(path: Path | None) -> tuple[str, str]:
    if path is None or not path.exists():
        text = DEFAULT_SYSTEM_FALLBACK
    else:
        text = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return text, digest


def _render_exemplars(exemplars: Sequence[Exemplar]) -> str:
    if not exemplars:
        return "(none — seed corpus empty; relying on convention spec only)"
    blocks = []
    for e in exemplars:
        blocks.append(
            f"## Example {e.comment_id} ({e.role}, {e.pr_url})\n"
            f"Diff context:\n```diff\n{e.diff_excerpt}\n```\n"
            f"Senior comment:\n> {e.body.strip()}"
        )
    return "\n\n".join(blocks)


_TRIM_CHARS = " .,!?·\t\n"


def postprocess(raw: str) -> str:
    cleaned = raw
    for pat in APPROVE_PATTERNS:
        cleaned = pat.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(_TRIM_CHARS)
    body = cleaned[len(PREFIX):].strip(_TRIM_CHARS) if cleaned.startswith(PREFIX) else cleaned
    if not body:
        body = "no surface-level concerns surfaced — human reviewer please inspect"
    return f"{PREFIX} {body}"
