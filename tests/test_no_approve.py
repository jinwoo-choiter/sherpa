"""Lock-in: the bot path never approves a PR.

Two layers per spec pre-flight-bot:
1. SOURCE GREP — the bot package's own source must not contain GitHub Reviews
   API surface. (We are intentionally strict; if you ever need to *read* review
   data, do it from a different package.)
2. RUNTIME TRANSPORT DOUBLE — wire a fake httpx transport into GitHubClient and
   assert that bot.post(...) only ever hits issues/comments endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from sherpa.bot import poster
from sherpa.config import Config


# ---- 1) SOURCE GREP ----

FORBIDDEN_NEEDLES = (
    "submitReview",
    "/reviews",
    '"event": "APPROVE"',
    "'event': 'APPROVE'",
    "PullRequestReview",
)


def test_bot_source_contains_no_review_api_surface() -> None:
    bot_dir = Path(poster.__file__).resolve().parent
    offenders: list[tuple[str, str]] = []
    for path in bot_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_NEEDLES:
            if needle in text:
                offenders.append((str(path), needle))
    assert not offenders, f"bot source references review-API surface: {offenders}"


# ---- 2) RUNTIME TRANSPORT DOUBLE ----

class _RecordingTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        # Minimal canned responses for the endpoints poster.py exercises.
        if request.method == "GET" and path == "/user":
            return httpx.Response(200, json={"login": "sherpa-bot"})
        if request.method == "GET" and path.endswith("/comments"):
            return httpx.Response(200, json=[])
        if request.method == "POST" and path.endswith("/comments"):
            return httpx.Response(201, json={"id": 1})
        if request.method == "PATCH" and "/issues/comments/" in path:
            return httpx.Response(200, json={"id": 1})
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})


@pytest.fixture
def fake_transport(monkeypatch: pytest.MonkeyPatch) -> _RecordingTransport:
    transport = _RecordingTransport()

    real_init = httpx.Client.__init__

    def fake_init(self: httpx.Client, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", fake_init)
    monkeypatch.setenv("SHERPA_GH_TOKEN", "x")
    return transport


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


def test_bot_post_only_hits_issue_comment_endpoints(
    tmp_path: Path,
    fake_transport: _RecordingTransport,
) -> None:
    cfg = _cfg(tmp_path)

    result = poster.post(cfg, "acme", "widgets", 7, "[pre-flight] body")

    assert result.action == "created"
    paths = [p for _, p in fake_transport.calls]
    # Allowed: /user, /issues/.../comments, /issues/comments/{id}.
    bad = [p for p in paths if "/reviews" in p or p.endswith("/reviews")]
    assert bad == [], f"bot called review endpoint(s): {bad}"
    # Sanity: a comments endpoint is among the calls.
    assert any("/comments" in p for p in paths), paths
    _ = json  # silence import
