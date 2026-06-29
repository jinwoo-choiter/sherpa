"""Auditable run log. Spec review-inference: every run logs PR id, diff slice,
spec version hash, and the injected knowledge/exemplar ids. For the agentic path
the record is extended with the agent's trajectory (agent/model, files read,
commands run, blocked attempts, raw transcript ref) so a nondeterministic run can
be reconstructed after the fact."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from sherpa.agent.schema import Trajectory


def write(
    audit_dir: Path,
    *,
    pr_id: str,
    diff_excerpt: str,
    spec_version_hash: str,
    exemplar_ids: tuple[str, ...],
    output_body: str,
    knowledge_ids: Sequence[str] | None = None,
    trajectory: Trajectory | None = None,
) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = audit_dir / f"{ts}-{_safe(pr_id)}.json"
    record: dict[str, object] = {
        "pr_id": pr_id,
        "spec_version_hash": spec_version_hash,
        "exemplar_ids": list(exemplar_ids),
        "diff_excerpt_first_400": diff_excerpt[:400],
        "output_body": output_body,
        "ts": ts,
    }
    if knowledge_ids is not None:
        record["knowledge_ids"] = list(knowledge_ids)
    if trajectory is not None:
        record["trajectory"] = {
            "agent_name": trajectory.agent_name,
            "model_id": trajectory.model_id,
            "agent_version": trajectory.agent_version,
            "files_read": list(trajectory.files_read),
            "commands_run": list(trajectory.commands_run),
            "blocked_attempts": list(trajectory.blocked_attempts),
            "raw_session_ref": trajectory.raw_session_ref,
        }
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)[:64]
