"""Top-N retrieval against the local index. Empty index returns zero results
(spec: 'still emits a pre-flight comment using only the spec layer')."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sherpa import db
from sherpa.config import Config
from sherpa.inference.llm import LLMClient


@dataclass(frozen=True)
class Retrieved:
    comment_id: str
    pr_url: str
    role: str
    body: str
    diff_excerpt: str
    score: float


def retrieve_for_pr(
    cfg: Config,
    conn: sqlite3.Connection,
    pr_id: str,
    top_n: int = 5,
) -> list[Retrieved]:
    diffs = db.fetch_pr_diffs(conn, pr_id)
    query_text = "\n\n".join(str(d["diff_text"])[:500] for d in diffs) or pr_id
    return _retrieve(cfg, query_text, top_n)


def _retrieve(cfg: Config, query_text: str, top_n: int) -> list[Retrieved]:
    arr_path = cfg.rag_index_dir / "embeddings.npy"
    meta_path = cfg.rag_index_dir / "meta.jsonl"
    if not arr_path.exists() or not meta_path.exists():
        return []

    arr = np.load(arr_path)
    if arr.size == 0 or arr.shape[0] == 0:
        return []

    with LLMClient(cfg.ollama_base_url, cfg.embedding_model) as llm:
        q = np.array(llm.embed(query_text), dtype=np.float32)

    qn = q / (np.linalg.norm(q) or 1.0)
    scores = arr @ qn  # both are L2-normalized → cosine similarity
    order = np.argsort(-scores)[: max(top_n, 0)]

    metas = _read_meta(meta_path)
    out: list[Retrieved] = []
    for idx in order:
        m = metas[int(idx)]
        out.append(
            Retrieved(
                comment_id=str(m["comment_id"]),
                pr_url=f"{m['repo']}#PR-{m['pr_number']}",
                role=str(m["role"]),
                body=str(m["body"]),
                diff_excerpt=str(m["diff_excerpt"]),
                score=float(scores[int(idx)]),
            )
        )
    return out


def _read_meta(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
