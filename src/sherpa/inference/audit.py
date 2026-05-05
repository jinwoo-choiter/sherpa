"""Auditable prompt log. Spec review-inference: every run logs PR id, diff slice,
spec version hash, and exemplar ids."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write(
    audit_dir: Path,
    *,
    pr_id: str,
    diff_excerpt: str,
    spec_version_hash: str,
    exemplar_ids: tuple[str, ...],
    output_body: str,
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = audit_dir / f"{ts}-{_safe(pr_id)}.json"
    path.write_text(
        json.dumps(
            {
                "pr_id": pr_id,
                "spec_version_hash": spec_version_hash,
                "exemplar_ids": list(exemplar_ids),
                "diff_excerpt_first_400": diff_excerpt[:400],
                "output_body": output_body,
                "ts": ts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:64]
