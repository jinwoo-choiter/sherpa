"""Heuristic classifier: a comment's resolution_type from on-disk evidence.

Per design D7, accuracy is not the goal — this is a learning-corpus filter.
We use the data already in SQLite (no live git checkout required), since
ingestion captures per-PR file diffs alongside review comments.

Inputs the classifier needs about a single comment:
- the comment row (file_path, line_range, created_at, body)
- the parent PR's status (merged?)
- the PR's diffs (file/line ranges of post-comment changes)
- subsequent comments on the same PR (count + bodies)

A real implementation would key 'post-comment' off commit timestamps; here we
use a simpler approximation: a diff covering the comment's file+line range is
considered "post-comment" if any later comment exists OR the PR was merged
after the comment. This is good enough as a filter.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# Small manual seed; expand by editing in place. Keep narrow — false positives
# here just classify a comment as 'dismissed' when it might be 'addressed'.
DISMISSAL_PATTERNS = (
    "intentional",
    "won't fix",
    "wontfix",
    "by design",
    "out of scope",
    "later",
    "follow-up",
    "follow up",
    "그대로",
    "의도된",
    "다음 PR",
    "별도 PR",
)


@dataclass(frozen=True)
class CommentEvidence:
    comment_id: str
    file_path: str | None
    line_range: str | None
    created_at: str
    pr_merged: bool
    follow_up_comment_count: int
    follow_up_bodies: tuple[str, ...]
    overlapping_diff_ids: tuple[str, ...]  # diffs that cover the comment's lines


def classify(ev: CommentEvidence) -> tuple[str, bool, str | None]:
    """Return (resolution_type, resulted_in_change, linked_diff_id)."""
    has_change = bool(ev.overlapping_diff_ids)
    linked = ev.overlapping_diff_ids[0] if ev.overlapping_diff_ids else None

    if has_change:
        if ev.follow_up_comment_count >= 5:
            return ("discussed", True, linked)
        return ("addressed", True, linked)

    if ev.pr_merged and _matches_dismissal(ev.follow_up_bodies):
        return ("dismissed", False, None)

    if ev.pr_merged and ev.follow_up_comment_count == 0:
        return ("ignored", False, None)

    # No code change AND there is some discussion AND PR isn't merged: treat as
    # 'discussed' (still in flight). resulted_in_change=False.
    if ev.follow_up_comment_count >= 5:
        return ("discussed", False, None)

    # Default: ignored. The PR may yet move; classifier can be re-run later.
    return ("ignored", False, None)


def _matches_dismissal(bodies: Iterable[str]) -> bool:
    joined = "\n".join(bodies).lower()
    return any(p in joined for p in DISMISSAL_PATTERNS)


def parse_line_range(s: str | None) -> tuple[int, int] | None:
    if not s:
        return None
    a, _, b = s.partition("-")
    try:
        return (int(a), int(b)) if b else (int(a), int(a))
    except ValueError:
        return None


def ranges_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]
