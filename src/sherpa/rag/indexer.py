"""Build the seed RAG index from senior+addressed comments.

Storage: a single .npz of float32 embeddings + a .jsonl of metadata, both under
cfg.rag_index_dir. Brute-force cosine retrieval is fine for MVP scale (months
of senior addressed comments — hundreds, maybe thousands).

Pre-weekly-review heuristic (review-inference seed corpus): senior author AND
resolution_type='addressed' AND parent PR merged. Once weekly review lands,
filtering will additionally require label='accept' (already supported by the
DB query in fetch_addressed_senior_comments).
"""

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
class IndexBuildResult:
    documents: int
    index_path: str
    meta_path: str


def build(cfg: Config) -> IndexBuildResult:
    cfg.rag_index_dir.mkdir(parents=True, exist_ok=True)

    with db.connect(cfg.db_path) as conn:
        rows = db.fetch_addressed_senior_comments(conn)
        documents = [_doc_for(row, conn) for row in rows]

    if not documents:
        # Empty index is valid; retriever handles missing files.
        _save(cfg, np.zeros((0, 1), dtype=np.float32), [])
        return IndexBuildResult(0, str(_index_path(cfg)), str(_meta_path(cfg)))

    with LLMClient(cfg.ollama_base_url, cfg.embedding_model) as llm:
        vectors = [llm.embed(d["embedding_text"]) for d in documents]

    arr = np.array(vectors, dtype=np.float32)
    arr = _normalize(arr)
    _save(cfg, arr, documents)

    return IndexBuildResult(
        documents=len(documents),
        index_path=str(_index_path(cfg)),
        meta_path=str(_meta_path(cfg)),
    )


def _doc_for(row: sqlite3.Row, conn: sqlite3.Connection) -> dict[str, object]:
    diff_excerpt = ""
    if row["linked_diff_id"]:
        d = conn.execute(
            "SELECT diff_text FROM code_diffs WHERE id = ?", (row["linked_diff_id"],),
        ).fetchone()
        if d:
            diff_excerpt = str(d["diff_text"])[:1000]
    body = str(row["body"] or "")
    return {
        "comment_id": str(row["id"]),
        "pr_id": str(row["pr_id"]),
        "repo": str(row["repo"]),
        "pr_number": int(row["pr_number"]),
        "role": str(row["role"]),
        "body": body,
        "diff_excerpt": diff_excerpt,
        "embedding_text": _embedding_text(diff_excerpt, body),
    }


def _embedding_text(diff_excerpt: str, body: str) -> str:
    return f"DIFF:\n{diff_excerpt}\n\nCOMMENT:\n{body}"


def _normalize(arr: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).astype(np.float32)


def _index_path(cfg: Config) -> Path:
    return cfg.rag_index_dir / "embeddings.npy"


def _meta_path(cfg: Config) -> Path:
    return cfg.rag_index_dir / "meta.jsonl"


def _save(cfg: Config, arr: np.ndarray, documents: list[dict[str, object]]) -> None:
    np.save(_index_path(cfg), arr)
    with _meta_path(cfg).open("w", encoding="utf-8") as f:
        for d in documents:
            d_out = {k: v for k, v in d.items() if k != "embedding_text"}
            f.write(json.dumps(d_out, ensure_ascii=False) + "\n")
