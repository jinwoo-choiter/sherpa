"""Audit record extends to the agent trajectory; legacy calls stay unchanged."""

from __future__ import annotations

import json

from sherpa.agent.schema import Trajectory
from sherpa.inference import audit


def test_audit_includes_trajectory(tmp_path):
    traj = Trajectory(
        agent_name="claude",
        model_id="m",
        files_read=("a.py",),
        commands_run=("git diff",),
        raw_session_ref="s1",
    )
    p = audit.write(
        tmp_path,
        pr_id="PR1",
        diff_excerpt="d",
        spec_version_hash="h",
        exemplar_ids=(),
        output_body="b",
        knowledge_ids=["k1"],
        trajectory=traj,
    )
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert rec["trajectory"]["agent_name"] == "claude"
    assert rec["trajectory"]["files_read"] == ["a.py"]
    assert rec["trajectory"]["raw_session_ref"] == "s1"
    assert rec["knowledge_ids"] == ["k1"]


def test_audit_legacy_call_omits_trajectory(tmp_path):
    p = audit.write(
        tmp_path,
        pr_id="PR1",
        diff_excerpt="d",
        spec_version_hash="h",
        exemplar_ids=("e1",),
        output_body="b",
    )
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert "trajectory" not in rec
    assert "knowledge_ids" not in rec
    assert rec["exemplar_ids"] == ["e1"]
