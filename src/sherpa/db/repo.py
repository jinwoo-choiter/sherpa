"""SQL helpers. Every read/write to the SQLite schema goes through this module.

Spec §4 schema. UPSERTs on primary keys make ingestion idempotent.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

SCHEMA_PATH = files("sherpa.db").joinpath("schema.sql")

VALID_RESOLUTIONS = {"addressed", "discussed", "dismissed", "ignored"}
VALID_ROLES = {"senior", "peer", "bot"}
VALID_KNOWLEDGE_STATUS = {"candidate", "active", "rejected"}


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_schema(conn: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)


def classify_role(login: str, seniors: frozenset[str], bots: frozenset[str]) -> str:
    if login in bots:
        return "bot"
    if login in seniors:
        return "senior"
    return "peer"


def _iso(ts: datetime | str | None) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat()
    return ts


def upsert_pr(
    conn: sqlite3.Connection,
    *,
    pr_id: str,
    repo: str,
    number: int,
    opened_at: datetime | str,
    merged_at: datetime | str | None,
    status: str,
    author_hash: str,
    cycle_time_hours: float | None,
) -> None:
    if status not in {"open", "merged", "closed"}:
        raise ValueError(f"invalid status: {status}")
    conn.execute(
        """
        INSERT INTO pull_requests (id, repo, number, opened_at, merged_at,
                                   status, author_hash, cycle_time_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            repo=excluded.repo,
            number=excluded.number,
            opened_at=excluded.opened_at,
            merged_at=excluded.merged_at,
            status=excluded.status,
            author_hash=excluded.author_hash,
            cycle_time_hours=excluded.cycle_time_hours
        """,
        (pr_id, repo, number, _iso(opened_at), _iso(merged_at),
         status, author_hash, cycle_time_hours),
    )


def upsert_review_comment(
    conn: sqlite3.Connection,
    *,
    comment_id: str,
    pr_id: str,
    author_hash: str,
    role: str,
    file_path: str | None,
    line_range: str | None,
    body: str,
    created_at: datetime | str,
    category: str | None = None,
) -> None:
    if role not in VALID_ROLES:
        raise ValueError(f"invalid role: {role}")
    conn.execute(
        """
        INSERT INTO review_comments (id, pr_id, author_hash, role, file_path,
                                     line_range, body, created_at, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            pr_id=excluded.pr_id,
            author_hash=excluded.author_hash,
            role=excluded.role,
            file_path=excluded.file_path,
            line_range=excluded.line_range,
            body=excluded.body,
            created_at=excluded.created_at,
            category=excluded.category
        """,
        (comment_id, pr_id, author_hash, role, file_path,
         line_range, body, _iso(created_at), category),
    )


def upsert_code_diff(
    conn: sqlite3.Connection,
    *,
    diff_id: str,
    pr_id: str,
    commit_sha: str,
    file_path: str,
    line_range: str,
    diff_text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO code_diffs (id, pr_id, commit_sha, file_path, line_range, diff_text)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            pr_id=excluded.pr_id,
            commit_sha=excluded.commit_sha,
            file_path=excluded.file_path,
            line_range=excluded.line_range,
            diff_text=excluded.diff_text
        """,
        (diff_id, pr_id, commit_sha, file_path, line_range, diff_text),
    )


def upsert_comment_outcome(
    conn: sqlite3.Connection,
    *,
    comment_id: str,
    resulted_in_change: bool,
    linked_diff_id: str | None,
    resolution_type: str,
) -> None:
    if resolution_type not in VALID_RESOLUTIONS:
        raise ValueError(f"invalid resolution_type: {resolution_type}")
    conn.execute(
        """
        INSERT INTO comment_outcomes (comment_id, resulted_in_change,
                                      linked_diff_id, resolution_type)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(comment_id) DO UPDATE SET
            resulted_in_change=excluded.resulted_in_change,
            linked_diff_id=excluded.linked_diff_id,
            resolution_type=excluded.resolution_type
        """,
        (comment_id, 1 if resulted_in_change else 0, linked_diff_id, resolution_type),
    )


def upsert_learning_label(
    conn: sqlite3.Connection,
    *,
    comment_id: str,
    label: str,
    labeled_by_hash: str,
    labeled_at: datetime | str,
    weekly_pr_url: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO learning_labels (comment_id, label, labeled_by_hash,
                                     labeled_at, weekly_pr_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(comment_id) DO UPDATE SET
            label=excluded.label,
            labeled_by_hash=excluded.labeled_by_hash,
            labeled_at=excluded.labeled_at,
            weekly_pr_url=excluded.weekly_pr_url
        """,
        (comment_id, label, labeled_by_hash, _iso(labeled_at), weekly_pr_url),
    )


def fetch_pr_comments(conn: sqlite3.Connection, pr_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM review_comments WHERE pr_id = ? ORDER BY created_at",
        (pr_id,),
    ))


def fetch_pr_diffs(conn: sqlite3.Connection, pr_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        "SELECT * FROM code_diffs WHERE pr_id = ?",
        (pr_id,),
    ))


def fetch_diff_by_id(conn: sqlite3.Connection, diff_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM code_diffs WHERE id = ?", (diff_id,)).fetchone()


# ---- knowledge-capture store ----

def insert_knowledge_candidate(
    conn: sqlite3.Connection,
    *,
    entry_id: str,
    body: str,
    source_comment_ids: list[str],
    diff_excerpt: str,
    created_at: datetime | str,
) -> bool:
    """Insert a candidate iff absent. Returns True if a new row was created.

    Existing entries (incl. confirmed/rejected) are left untouched, so re-running
    distillation never clobbers a curation decision.
    """
    cur = conn.execute(
        """
        INSERT INTO knowledge_entries (id, status, body, source_comment_ids,
                                       diff_excerpt, created_at)
        VALUES (?, 'candidate', ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (entry_id, body, json.dumps(source_comment_ids), diff_excerpt, _iso(created_at)),
    )
    return cur.rowcount > 0


def set_knowledge_status(conn: sqlite3.Connection, *, entry_id: str, status: str) -> None:
    if status not in VALID_KNOWLEDGE_STATUS:
        raise ValueError(f"invalid knowledge status: {status}")
    conn.execute(
        "UPDATE knowledge_entries SET status = ? WHERE id = ?",
        (status, entry_id),
    )


def fetch_knowledge(conn: sqlite3.Connection, status: str | None = None) -> list[sqlite3.Row]:
    if status is not None:
        if status not in VALID_KNOWLEDGE_STATUS:
            raise ValueError(f"invalid knowledge status: {status}")
        return list(conn.execute(
            "SELECT * FROM knowledge_entries WHERE status = ? ORDER BY created_at",
            (status,),
        ))
    return list(conn.execute("SELECT * FROM knowledge_entries ORDER BY created_at"))


def fetch_addressed_senior_comments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Comments eligible for the auto-pass heuristic seed corpus.

    Senior author + comment_outcomes.resolution_type='addressed' + parent PR merged.
    Pre-weekly-review fallback per spec review-inference.
    """
    return list(conn.execute(
        """
        SELECT rc.*, co.linked_diff_id, p.repo, p.number AS pr_number
        FROM review_comments rc
        JOIN comment_outcomes co ON co.comment_id = rc.id
        JOIN pull_requests p ON p.id = rc.pr_id
        LEFT JOIN learning_labels ll ON ll.comment_id = rc.id
        WHERE rc.role = 'senior'
          AND co.resolution_type = 'addressed'
          AND p.status = 'merged'
          AND (ll.label IS NULL OR ll.label = 'accept')
        """,
    ))


def execute(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
    """Escape hatch for ad-hoc operator-side reporting (used by README SQL).

    Production modules should use the typed helpers above.
    """
    return conn.execute(sql, params)
