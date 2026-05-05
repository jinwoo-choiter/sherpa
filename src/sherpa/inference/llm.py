"""Ollama wrapper. Local-only by hard contract.

Spec review-inference: 'no external LLM API'. We refuse any base URL outside
loopback / link-local / RFC1918, evaluated at every call (not just at import),
so a runtime config swap can't escape the guard.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx


class RemoteEndpointError(RuntimeError):
    """Raised when the configured Ollama URL points outside the local machine."""


def _assert_local(url: str) -> None:
    host = urlparse(url).hostname or ""
    if host in {"localhost", ""}:
        return
    try:
        ip = ipaddress.ip_address(host)
    except ValueError as exc:
        raise RemoteEndpointError(
            f"Ollama URL host '{host}' is not an IP literal or localhost; "
            f"refusing — review-inference forbids remote endpoints."
        ) from exc
    if not (ip.is_loopback or ip.is_private or ip.is_link_local):
        raise RemoteEndpointError(
            f"Ollama URL host '{host}' resolves to a non-local IP; refusing."
        )


class LLMClient:
    def __init__(self, base_url: str, model: str, timeout: float = 600.0) -> None:
        _assert_local(base_url)
        self._base = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def generate(self, prompt: str) -> str:
        _assert_local(self._base)  # second check; defends against base mutation
        resp = self._client.post(
            f"{self._base}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        out = data.get("response")
        if not isinstance(out, str):
            raise RuntimeError(f"unexpected Ollama response shape: {data!r}")
        return out

    def embed(self, text: str) -> list[float]:
        _assert_local(self._base)
        resp = self._client.post(
            f"{self._base}/api/embeddings",
            json={"model": self._model, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        emb = data.get("embedding")
        if not isinstance(emb, list) or not all(isinstance(x, (int, float)) for x in emb):
            raise RuntimeError(f"unexpected Ollama embedding shape: {data!r}")
        return [float(x) for x in emb]
