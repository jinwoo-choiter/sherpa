"""Daily PR / comment polling. Spec pr-data-ingestion.

Watermark: a JSON state file holds the last successful per-repo timestamp. The
watermark is advanced ONLY after the entire batch commits — a partial failure
re-fetches the unfinished window on the next run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sherpa import db
from sherpa.anon import author_hash
from sherpa.config import Config
from sherpa.ingester.github import GitHubClient


@dataclass(frozen=True)
class PollResult:
    repo: str
    prs_seen: int
    comments_seen: int
    diffs_seen: int


def _load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _hash(cfg: Config, login: str | None) -> str:
    return author_hash(cfg.salt, login or "ghost")


def _pr_status(pr: dict[str, object]) -> str:
    if pr.get("merged_at"):
        return "merged"
    state = pr.get("state")
    if state == "closed":
        return "closed"
    return "open"


def _cycle_hours(opened: str | None, merged: str | None) -> float | None:
    if not opened or not merged:
        return None
    try:
        a = datetime.fromisoformat(opened.replace("Z", "+00:00"))
        b = datetime.fromisoformat(merged.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (b - a).total_seconds() / 3600.0


def poll_repo(cfg: Config, owner: str, repo: str) -> PollResult:
    """Idempotent poll. Walks pulls (sorted by updated DESC) until we see records
    older than the watermark, then ingests their comments and diff files."""
    state = _load_state(cfg.state_path)
    watermark = state.get(f"{owner}/{repo}")
    repo_full = f"{owner}/{repo}"

    prs_seen = 0
    comments_seen = 0
    diffs_seen = 0
    new_watermark: str | None = None

    with GitHubClient() as gh, db.connect(cfg.db_path) as conn:
        db.init_schema(conn)
        conn.execute("BEGIN")
        try:
            for pr in gh.list_pulls(owner, repo, state="all"):
                updated_at_obj = pr.get("updated_at")
                if not isinstance(updated_at_obj, str):
                    continue
                updated_at = updated_at_obj
                if new_watermark is None:
                    new_watermark = updated_at  # first item = newest
                if watermark and updated_at <= watermark:
                    break

                pr_id = str(pr["node_id"])
                number = int(pr["number"])
                user = pr.get("user") or {}
                login = user.get("login") if isinstance(user, dict) else None
                opened_at = str(pr["created_at"])
                merged_at_raw = pr.get("merged_at")
                merged_at = str(merged_at_raw) if isinstance(merged_at_raw, str) else None

                db.upsert_pr(
                    conn,
                    pr_id=pr_id,
                    repo=repo_full,
                    number=number,
                    opened_at=opened_at,
                    merged_at=merged_at,
                    status=_pr_status(pr),
                    author_hash=_hash(cfg, login if isinstance(login, str) else None),
                    cycle_time_hours=_cycle_hours(opened_at, merged_at),
                )
                prs_seen += 1

                comments_seen += _ingest_comments(cfg, gh, conn, owner, repo, number, pr_id)
                diffs_seen += _ingest_diffs(gh, conn, owner, repo, number, pr_id)

            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    if new_watermark is not None and prs_seen > 0:
        state[f"{owner}/{repo}"] = new_watermark
        _save_state(cfg.state_path, state)

    return PollResult(
        repo=repo_full,
        prs_seen=prs_seen,
        comments_seen=comments_seen,
        diffs_seen=diffs_seen,
    )


def _ingest_comments(
    cfg: Config,
    gh: GitHubClient,
    conn: object,  # sqlite3.Connection — kept loose for readability
    owner: str,
    repo: str,
    number: int,
    pr_id: str,
) -> int:
    seen = 0
    # Review (line-level) comments.
    for c in gh.list_pr_review_comments(owner, repo, number):
        seen += 1
        login = (c.get("user") or {}).get("login")
        role = db.classify_role(login or "", cfg.seniors, cfg.bots)
        line_range = _line_range(c.get("original_start_line"), c.get("original_line"))
        db.upsert_review_comment(
            conn,  # type: ignore[arg-type]
            comment_id=str(c["node_id"]),
            pr_id=pr_id,
            author_hash=_hash(cfg, login),
            role=role,
            file_path=c.get("path"),
            line_range=line_range,
            body=str(c.get("body") or ""),
            created_at=str(c["created_at"]),
        )
    # Issue (PR-level) comments.
    for c in gh.list_pr_issue_comments(owner, repo, number):
        seen += 1
        login = (c.get("user") or {}).get("login")
        role = db.classify_role(login or "", cfg.seniors, cfg.bots)
        db.upsert_review_comment(
            conn,  # type: ignore[arg-type]
            comment_id=str(c["node_id"]),
            pr_id=pr_id,
            author_hash=_hash(cfg, login),
            role=role,
            file_path=None,
            line_range=None,
            body=str(c.get("body") or ""),
            created_at=str(c["created_at"]),
        )
    return seen


def _ingest_diffs(
    gh: GitHubClient,
    conn: object,
    owner: str,
    repo: str,
    number: int,
    pr_id: str,
) -> int:
    seen = 0
    # We attribute file-level diffs to the PR head commit. For per-commit blame
    # we re-walk commits in outcomes/, where it actually matters.
    head_sha: str | None = None
    for commit in gh.list_pr_commits(owner, repo, number):
        head_sha = str(commit.get("sha") or head_sha)
    if head_sha is None:
        return 0
    for f in gh.get_pr_files(owner, repo, number):
        path = str(f.get("filename") or "")
        if not path:
            continue
        patch = str(f.get("patch") or "")
        diff_id = f"{pr_id}:{head_sha}:{path}"
        db.upsert_code_diff(
            conn,  # type: ignore[arg-type]
            diff_id=diff_id,
            pr_id=pr_id,
            commit_sha=head_sha,
            file_path=path,
            line_range=_diff_line_range(patch),
            diff_text=patch,
        )
        seen += 1
    return seen


def _line_range(start: object, end: object) -> str | None:
    if not isinstance(end, int):
        return None
    s = start if isinstance(start, int) else end
    return f"{s}-{end}"


def _diff_line_range(patch: str) -> str:
    # "@@ -a,b +c,d @@" — take the new-file range. Fallback to "0-0" if absent.
    for line in patch.splitlines():
        if line.startswith("@@"):
            try:
                plus = line.split("+", 1)[1].split(" ", 1)[0]
                start_str, _, length_str = plus.partition(",")
                start = int(start_str)
                length = int(length_str) if length_str else 1
                return f"{start}-{start + max(length - 1, 0)}"
            except (IndexError, ValueError):
                return "0-0"
    return "0-0"
