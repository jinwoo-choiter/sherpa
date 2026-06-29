"""Operator-controlled configuration: salt, paths, role mapping.

Salt file is the single anchor for §2.2 anonymization. Missing salt → fail-fast
(spec pr-data-ingestion: "Salt is missing at startup").
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    salt: str
    db_path: Path
    seniors: frozenset[str]  # GitHub logins classified as 'senior'
    bots: frozenset[str]     # GitHub logins classified as 'bot' (incl. sherpa-bot)
    rag_index_dir: Path
    audit_dir: Path
    state_path: Path
    skill_md_path: Path | None  # convention spec; lives in a separate repo per D8
    ollama_base_url: str
    llm_model: str
    embedding_model: str
    review_agent: str  # default CLI agent name; per-run --agent overrides it


def load() -> Config:
    salt_path_env = os.environ.get("SHERPA_SALT_PATH")
    if not salt_path_env:
        raise ConfigError(
            "SHERPA_SALT_PATH is not set. Anonymization salt is required at startup; "
            "refusing to ingest un-salted data."
        )
    salt_path = Path(salt_path_env).expanduser()
    if not salt_path.is_file():
        raise ConfigError(f"Salt file not found at {salt_path}")
    salt = salt_path.read_text(encoding="utf-8").strip()
    if not salt:
        raise ConfigError(f"Salt file at {salt_path} is empty")

    seniors_path = os.environ.get("SHERPA_SENIORS_PATH")
    bots_path = os.environ.get("SHERPA_BOTS_PATH")
    seniors = _read_login_set(seniors_path)
    bots = _read_login_set(bots_path)

    db_path = Path(os.environ.get("SHERPA_DB_PATH", "./sherpa.sqlite")).expanduser()
    rag_dir = Path(os.environ.get("SHERPA_RAG_DIR", "./rag_index")).expanduser()
    audit_dir = Path(os.environ.get("SHERPA_AUDIT_DIR", "./audit")).expanduser()
    state_path = Path(os.environ.get("SHERPA_STATE_PATH", "./.sherpa/state.json")).expanduser()
    skill_md = os.environ.get("SHERPA_SKILL_MD")
    skill_md_path = Path(skill_md).expanduser() if skill_md else None

    return Config(
        salt=salt,
        db_path=db_path,
        seniors=seniors,
        bots=bots,
        rag_index_dir=rag_dir,
        audit_dir=audit_dir,
        state_path=state_path,
        skill_md_path=skill_md_path,
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        llm_model=os.environ.get("SHERPA_LLM_MODEL", "qwen2.5-coder:32b-instruct-q4_K_M"),
        # TODO(operator): compare 2-3 embedding candidates and revisit (tasks.md 5.1).
        embedding_model=os.environ.get("SHERPA_EMBED_MODEL", "nomic-embed-text"),
        review_agent=os.environ.get("SHERPA_REVIEW_AGENT", "claude"),
    )


def _read_login_set(path_str: str | None) -> frozenset[str]:
    if not path_str:
        return frozenset()
    p = Path(path_str).expanduser()
    if not p.is_file():
        raise ConfigError(f"Login set file not found at {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(x, str) for x in data):
        raise ConfigError(f"{p} must be a JSON array of GitHub login strings")
    return frozenset(data)
