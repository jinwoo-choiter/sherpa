"""Tacit-knowledge store (capability knowledge-capture).

Candidates are distilled from good-cases-only outcomes (senior + addressed +
merged). A human curation gate promotes candidates to `active`; only active
entries are injected into reviews. Provenance is comment ids only — never a
plaintext login (D5/D10).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sherpa import db
from sherpa.config import Config


@dataclass(frozen=True)
class KnowledgeEntry:
    id: str
    status: str
    body: str
    source_comment_ids: tuple[str, ...]
    diff_excerpt: str


def _entry_id(source_comment_ids: list[str]) -> str:
    h = hashlib.sha256()
    h.update(b"knowledge\x00")
    h.update("\x00".join(sorted(source_comment_ids)).encode("utf-8"))
    return h.hexdigest()[:16]


def _to_entry(row: object) -> KnowledgeEntry:
    return KnowledgeEntry(
        id=str(row["id"]),  # type: ignore[index]
        status=str(row["status"]),  # type: ignore[index]
        body=str(row["body"]),  # type: ignore[index]
        source_comment_ids=tuple(json.loads(row["source_comment_ids"])),  # type: ignore[index]
        diff_excerpt=str(row["diff_excerpt"]),  # type: ignore[index]
    )


def distill(cfg: Config) -> int:
    """Create candidate entries from the good-cases-only corpus. Idempotent:
    existing entries (incl. confirmed/rejected) are left untouched, so a rejected
    candidate is never re-proposed from the same source."""
    created = 0
    now = datetime.now(UTC)
    with db.connect(cfg.db_path) as conn:
        for r in db.fetch_addressed_senior_comments(conn):
            comment_id = str(r["id"])
            diff_excerpt = ""
            linked = r["linked_diff_id"]
            if linked:
                d = db.fetch_diff_by_id(conn, str(linked))
                if d is not None:
                    diff_excerpt = str(d["diff_text"])[:1000]
            if db.insert_knowledge_candidate(
                conn,
                entry_id=_entry_id([comment_id]),
                body=str(r["body"]),
                source_comment_ids=[comment_id],
                diff_excerpt=diff_excerpt,
                created_at=now,
            ):
                created += 1
    return created


def set_status(cfg: Config, entry_id: str, status: str) -> None:
    with db.connect(cfg.db_path) as conn:
        db.set_knowledge_status(conn, entry_id=entry_id, status=status)


def listing(cfg: Config, status: str | None = None) -> list[KnowledgeEntry]:
    with db.connect(cfg.db_path) as conn:
        return [_to_entry(r) for r in db.fetch_knowledge(conn, status)]


def active_entries(conn: object) -> list[KnowledgeEntry]:
    return [_to_entry(r) for r in db.fetch_knowledge(conn, "active")]  # type: ignore[arg-type]
