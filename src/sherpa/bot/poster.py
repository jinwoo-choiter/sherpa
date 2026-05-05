"""Idempotent pre-flight comment poster.

Find an existing [pre-flight] comment authored by the bot identity; PATCH it if
present, POST a new one otherwise. Uses ONLY the issues/comments endpoints —
never reviews. (Tested in tests/test_no_approve.py.)
"""

from __future__ import annotations

from dataclasses import dataclass

from sherpa.config import Config
from sherpa.inference.prompt import PREFIX
from sherpa.ingester.github import GitHubClient


class IdentityError(RuntimeError):
    """Raised when the configured token does not resolve to a bot account."""


@dataclass(frozen=True)
class PostResult:
    action: str  # 'created' or 'updated'
    comment_id: int


def assert_bot_identity(gh: GitHubClient, cfg: Config) -> str:
    login = gh.viewer_login()
    if not cfg.bots:
        raise IdentityError(
            "SHERPA_BOTS_PATH is not configured; refusing to post without a known bot allowlist."
        )
    if login not in cfg.bots:
        raise IdentityError(
            f"Token belongs to '{login}', which is NOT in the bot allowlist "
            f"({sorted(cfg.bots)}). Pre-flight bot must run as a dedicated bot account."
        )
    return login


def post(cfg: Config, owner: str, repo: str, number: int, body: str) -> PostResult:
    if not body.startswith(PREFIX):
        # Defense in depth — the inference layer also enforces this.
        body = f"{PREFIX} {body}"

    with GitHubClient() as gh:
        bot_login = assert_bot_identity(gh, cfg)
        existing = _find_existing(gh, owner, repo, number, bot_login)
        if existing is not None:
            gh.patch_issue_comment(owner, repo, existing, body)
            return PostResult("updated", existing)
        created = gh.post_issue_comment(owner, repo, number, body)
        return PostResult("created", int(created["id"]))


def _find_existing(
    gh: GitHubClient, owner: str, repo: str, number: int, bot_login: str,
) -> int | None:
    for c in gh.list_pr_issue_comments(owner, repo, number):
        user = c.get("user") or {}
        login = user.get("login") if isinstance(user, dict) else None
        if login != bot_login:
            continue
        body = c.get("body") or ""
        if isinstance(body, str) and body.startswith(PREFIX):
            return int(c["id"])
    return None
