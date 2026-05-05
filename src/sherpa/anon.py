"""Author anonymization. Spec §2.2 / pr-data-ingestion: GitHub logins never persist as plaintext."""

from __future__ import annotations

import hashlib


def author_hash(salt: str, login: str) -> str:
    if not salt:
        raise ValueError("salt must be non-empty; refusing to compute un-salted hash")
    if not login:
        raise ValueError("login must be non-empty")
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(b"\x00")
    h.update(login.encode("utf-8"))
    return h.hexdigest()
