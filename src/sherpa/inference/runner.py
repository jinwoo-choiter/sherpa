"""Top-level inference run: PR id -> pre-flight body string."""

from __future__ import annotations

from dataclasses import dataclass

from sherpa import db
from sherpa.config import Config
from sherpa.inference import audit
from sherpa.inference.llm import LLMClient
from sherpa.inference.prompt import Exemplar, assemble, postprocess
from sherpa.rag.retriever import retrieve_for_pr


@dataclass(frozen=True)
class RunResult:
    body: str
    audit_path: str
    exemplar_ids: tuple[str, ...]


def run(cfg: Config, pr_id: str, top_n: int = 5) -> RunResult:
    with db.connect(cfg.db_path) as conn:
        pr = conn.execute(
            "SELECT id, repo, number FROM pull_requests WHERE id = ?", (pr_id,),
        ).fetchone()
        if pr is None:
            raise ValueError(f"unknown PR id: {pr_id}")
        diffs = db.fetch_pr_diffs(conn, pr_id)
        diff_text = _join_diffs(diffs)
        retrieved = retrieve_for_pr(cfg, conn, pr_id, top_n=top_n)

    exemplars = [
        Exemplar(
            comment_id=r.comment_id,
            pr_url=r.pr_url,
            role=r.role,
            body=r.body,
            diff_excerpt=r.diff_excerpt,
        )
        for r in retrieved
    ]

    prompt = assemble(skill_md_path=cfg.skill_md_path, exemplars=exemplars, pr_diff=diff_text)

    with LLMClient(cfg.ollama_base_url, cfg.llm_model) as llm:
        raw = llm.generate(prompt.text)
    body = postprocess(raw)

    log_path = audit.write(
        cfg.audit_dir,
        pr_id=pr_id,
        diff_excerpt=diff_text,
        spec_version_hash=prompt.spec_version_hash,
        exemplar_ids=prompt.exemplar_ids,
        output_body=body,
    )

    return RunResult(body=body, audit_path=str(log_path), exemplar_ids=prompt.exemplar_ids)


def _join_diffs(diffs: list[object]) -> str:
    chunks = []
    for d in diffs:
        # sqlite3.Row supports key access
        chunks.append(f"--- {d['file_path']} ({d['line_range']})\n{d['diff_text']}")  # type: ignore[index]
    return "\n\n".join(chunks)
