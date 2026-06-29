"""Knowledge capture: distillation (good-cases-only, idempotent), curation gate,
relevance injection, anonymized provenance."""

from __future__ import annotations

from pathlib import Path

import sherpa.db as db
from sherpa.config import Config
from sherpa.knowledge import inject, store


def _cfg(tmp_path: Path) -> Config:
    return Config(
        salt="dummy",
        db_path=tmp_path / "db.sqlite",
        seniors=frozenset(),
        bots=frozenset({"sherpa-bot"}),
        rag_index_dir=tmp_path / "rag",
        audit_dir=tmp_path / "audit",
        state_path=tmp_path / "state.json",
        skill_md_path=None,
        ollama_base_url="http://127.0.0.1:11434",
        llm_model="x",
        embedding_model="y",
        review_agent="claude",
    )


def _seed(cfg: Config) -> None:
    with db.connect(cfg.db_path) as conn:
        db.init_schema(conn)
        db.upsert_pr(
            conn, pr_id="PR1", repo="o/r", number=1,
            opened_at="2026-01-01T00:00:00", merged_at="2026-01-02T00:00:00",
            status="merged", author_hash="ah1", cycle_time_hours=24.0,
        )
        db.upsert_code_diff(
            conn, diff_id="D1", pr_id="PR1", commit_sha="sha",
            file_path="src/lock.py", line_range="10-20",
            diff_text="def acquire(): lock.acquire()  # EtherCAT cycle boundary",
        )
        db.upsert_review_comment(
            conn, comment_id="C1", pr_id="PR1", author_hash="senior_hash", role="senior",
            file_path="src/lock.py", line_range="10-20",
            body="hold the lock across the whole EtherCAT cycle, not per iteration",
            created_at="2026-01-01T01:00:00",
        )
        db.upsert_comment_outcome(
            conn, comment_id="C1", resulted_in_change=True,
            linked_diff_id="D1", resolution_type="addressed",
        )


def test_distill_creates_candidate_with_provenance(tmp_path):
    cfg = _cfg(tmp_path)
    _seed(cfg)
    assert store.distill(cfg) == 1
    entries = store.listing(cfg)
    assert len(entries) == 1
    e = entries[0]
    assert e.status == "candidate"
    assert e.source_comment_ids == ("C1",)          # provenance is comment id, not a login
    assert "EtherCAT" in e.diff_excerpt
    assert "senior_hash" not in e.body               # no author identity leaks into the entry


def test_distill_is_idempotent(tmp_path):
    cfg = _cfg(tmp_path)
    _seed(cfg)
    assert store.distill(cfg) == 1
    assert store.distill(cfg) == 0                   # same source → no duplicate


def test_rejected_candidate_not_reproposed(tmp_path):
    cfg = _cfg(tmp_path)
    _seed(cfg)
    store.distill(cfg)
    entry_id = store.listing(cfg)[0].id
    store.set_status(cfg, entry_id, "rejected")
    assert store.distill(cfg) == 0                   # rejection survives re-distillation
    assert store.listing(cfg, "rejected")[0].id == entry_id


def test_curation_gate_active_only(tmp_path):
    cfg = _cfg(tmp_path)
    _seed(cfg)
    store.distill(cfg)
    # candidate is not yet active
    assert store.listing(cfg, "active") == []
    entry_id = store.listing(cfg)[0].id
    store.set_status(cfg, entry_id, "active")
    assert [e.id for e in store.listing(cfg, "active")] == [entry_id]


def test_injection_relevance_and_empty_store(tmp_path):
    cfg = _cfg(tmp_path)
    _seed(cfg)
    store.distill(cfg)
    entry_id = store.listing(cfg)[0].id
    store.set_status(cfg, entry_id, "active")
    actives = store.listing(cfg, "active")

    relevant = inject.select_relevant(actives, "patch to EtherCAT lock acquire path", top_n=5)
    assert [e.id for e in relevant] == [entry_id]
    assert entry_id in inject.render(relevant)

    # unrelated diff → nothing injected
    assert inject.select_relevant(actives, "update frontend button colors", top_n=5) == []
    # empty active store → nothing injected (spec-layer-only fallback)
    assert inject.select_relevant([], "anything", top_n=5) == []
