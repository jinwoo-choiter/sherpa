"""Relevance + rendering for knowledge injection at review time.

Selects the active entries most relevant to the current PR diff and renders them
into the text block that `agent.build_prompt` injects. Relevance is a simple
token-overlap score for the MVP (no embedding dependency); an embedding-based
scorer reusing the RAG index is the planned upgrade (design Open Question).
An empty store yields no injection, so the review falls back to the spec layer.
"""

from __future__ import annotations

import re

from sherpa.knowledge.store import KnowledgeEntry

_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text)}


def _score(entry: KnowledgeEntry, pr_tokens: set[str]) -> int:
    entry_tokens = _tokens(f"{entry.body}\n{entry.diff_excerpt}")
    return len(pr_tokens & entry_tokens)


def select_relevant(
    entries: list[KnowledgeEntry],
    pr_diff_text: str,
    top_n: int = 5,
) -> list[KnowledgeEntry]:
    pr_tokens = _tokens(pr_diff_text)
    scored = [(e, _score(e, pr_tokens)) for e in entries]
    ranked = sorted(scored, key=lambda x: x[1], reverse=True)
    return [e for e, s in ranked if s > 0][: max(top_n, 0)]


def render(entries: list[KnowledgeEntry]) -> str:
    if not entries:
        return ""
    return "\n\n".join(f"## {e.id}\n{e.body.strip()}" for e in entries)
