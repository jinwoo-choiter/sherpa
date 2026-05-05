"""Recompute comment_outcomes for one or all PRs in the local SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from sherpa import db
from sherpa.config import Config
from sherpa.outcomes.classifier import (
    CommentEvidence,
    classify,
    parse_line_range,
    ranges_overlap,
)


@dataclass(frozen=True)
class RunResult:
    comments_classified: int
    addressed: int
    discussed: int
    dismissed: int
    ignored: int


def recompute_pr(cfg: Config, pr_id: str) -> RunResult:
    with db.connect(cfg.db_path) as conn:
        return _recompute(conn, pr_id)


def recompute_all(cfg: Config) -> RunResult:
    with db.connect(cfg.db_path) as conn:
        rows = list(conn.execute("SELECT id FROM pull_requests"))
        totals = RunResult(0, 0, 0, 0, 0)
        for row in rows:
            r = _recompute(conn, str(row["id"]))
            totals = RunResult(
                totals.comments_classified + r.comments_classified,
                totals.addressed + r.addressed,
                totals.discussed + r.discussed,
                totals.dismissed + r.dismissed,
                totals.ignored + r.ignored,
            )
        return totals


def _recompute(conn: sqlite3.Connection, pr_id: str) -> RunResult:
    pr_row = conn.execute(
        "SELECT id, status FROM pull_requests WHERE id = ?",
        (pr_id,),
    ).fetchone()
    if pr_row is None:
        return RunResult(0, 0, 0, 0, 0)
    pr_merged = pr_row["status"] == "merged"

    comments = db.fetch_pr_comments(conn, pr_id)
    diffs = db.fetch_pr_diffs(conn, pr_id)

    addressed = discussed = dismissed = ignored = 0
    classified = 0

    conn.execute("BEGIN")
    try:
        for c in comments:
            evidence = _build_evidence(c, comments, diffs, pr_merged)
            resolution, changed, linked = classify(evidence)
            db.upsert_comment_outcome(
                conn,
                comment_id=str(c["id"]),
                resulted_in_change=changed,
                linked_diff_id=linked,
                resolution_type=resolution,
            )
            classified += 1
            if resolution == "addressed":
                addressed += 1
            elif resolution == "discussed":
                discussed += 1
            elif resolution == "dismissed":
                dismissed += 1
            elif resolution == "ignored":
                ignored += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return RunResult(classified, addressed, discussed, dismissed, ignored)


def _build_evidence(
    c: sqlite3.Row,
    all_comments: list[sqlite3.Row],
    diffs: list[sqlite3.Row],
    pr_merged: bool,
) -> CommentEvidence:
    file_path = c["file_path"]
    line_range = parse_line_range(c["line_range"])

    overlapping: list[str] = []
    if file_path is not None and line_range is not None:
        for d in diffs:
            if d["file_path"] != file_path:
                continue
            d_range = parse_line_range(d["line_range"])
            if d_range is None:
                continue
            if ranges_overlap(line_range, d_range):
                overlapping.append(str(d["id"]))

    follow_ups = [r for r in all_comments if r["created_at"] > c["created_at"] and r["id"] != c["id"]]
    return CommentEvidence(
        comment_id=str(c["id"]),
        file_path=file_path,
        line_range=c["line_range"],
        created_at=str(c["created_at"]),
        pr_merged=pr_merged,
        follow_up_comment_count=len(follow_ups),
        follow_up_bodies=tuple(str(r["body"] or "") for r in follow_ups),
        overlapping_diff_ids=tuple(overlapping),
    )
