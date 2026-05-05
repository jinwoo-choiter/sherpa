"""Thin httpx wrapper around the GitHub REST API.

Auth via SHERPA_GH_TOKEN. Handles primary rate-limit (sleep until reset) and
secondary abuse-detection backoff. No external services beyond GitHub.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any

import httpx

API = "https://api.github.com"
USER_AGENT = "sherpa-bot (pre-flight reviewer; never approves)"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self.token = token or os.environ.get("SHERPA_GH_TOKEN")
        if not self.token:
            raise GitHubError("SHERPA_GH_TOKEN is not set")
        self._client = httpx.Client(
            base_url=API,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": USER_AGENT,
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---- core request with retry ----

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        for attempt in range(5):
            resp = self._client.request(method, path, **kw)
            if resp.status_code == 200 or resp.status_code == 201:
                return resp
            if resp.status_code in (403, 429) and self._is_rate_limited(resp):
                self._sleep_until_reset(resp)
                continue
            if resp.status_code in (502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise GitHubError(f"{method} {path} -> {resp.status_code}: {resp.text[:200]}")
        raise GitHubError(f"{method} {path} retried out")

    @staticmethod
    def _is_rate_limited(resp: httpx.Response) -> bool:
        return resp.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in resp.text.lower()

    @staticmethod
    def _sleep_until_reset(resp: httpx.Response) -> None:
        reset = resp.headers.get("X-RateLimit-Reset")
        if not reset:
            time.sleep(60)
            return
        wait = max(0, int(reset) - int(time.time())) + 1
        time.sleep(min(wait, 900))

    # ---- paged GET ----

    def _paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        page = 1
        params = dict(params or {})
        params.setdefault("per_page", 100)
        while True:
            params["page"] = page
            resp = self._request("GET", path, params=params)
            items = resp.json()
            if not isinstance(items, list):
                raise GitHubError(f"expected list from {path}, got {type(items)}")
            yield from items
            if len(items) < params["per_page"]:
                return
            page += 1

    # ---- typed endpoints used by the ingester ----

    def list_pulls(self, owner: str, repo: str, state: str = "all") -> Iterator[dict[str, Any]]:
        # Sorted by updated DESC so we can stop early once we see only stale updates.
        yield from self._paginate(
            f"/repos/{owner}/{repo}/pulls",
            {"state": state, "sort": "updated", "direction": "desc"},
        )

    def list_pr_review_comments(self, owner: str, repo: str, number: int) -> Iterator[dict[str, Any]]:
        yield from self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/comments")

    def list_pr_issue_comments(self, owner: str, repo: str, number: int) -> Iterator[dict[str, Any]]:
        yield from self._paginate(f"/repos/{owner}/{repo}/issues/{number}/comments")

    def list_pr_commits(self, owner: str, repo: str, number: int) -> Iterator[dict[str, Any]]:
        yield from self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/commits")

    def get_pr_files(self, owner: str, repo: str, number: int) -> Iterator[dict[str, Any]]:
        yield from self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/files")

    def viewer_login(self) -> str:
        resp = self._request("GET", "/user")
        login = resp.json().get("login")
        if not isinstance(login, str):
            raise GitHubError("/user returned no login")
        return login

    def post_issue_comment(self, owner: str, repo: str, number: int, body: str) -> dict[str, Any]:
        resp = self._request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            json={"body": body},
        )
        result: dict[str, Any] = resp.json()
        return result

    def patch_issue_comment(self, owner: str, repo: str, comment_id: int, body: str) -> dict[str, Any]:
        resp = self._request(
            "PATCH",
            f"/repos/{owner}/{repo}/issues/comments/{comment_id}",
            json={"body": body},
        )
        result: dict[str, Any] = resp.json()
        return result
