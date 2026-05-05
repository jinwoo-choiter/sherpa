"""Anonymization invariants. Spec pr-data-ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from sherpa import config as config_mod
from sherpa.anon import author_hash


def test_hash_is_deterministic_and_salt_dependent() -> None:
    a1 = author_hash("salt-a", "octocat")
    a2 = author_hash("salt-a", "octocat")
    b = author_hash("salt-b", "octocat")
    assert a1 == a2
    assert a1 != b


def test_hash_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError):
        author_hash("", "x")
    with pytest.raises(ValueError):
        author_hash("salt", "")


def test_config_load_fails_without_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SHERPA_SALT_PATH", raising=False)
    with pytest.raises(config_mod.ConfigError):
        config_mod.load()


def test_config_load_fails_when_salt_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SHERPA_SALT_PATH", str(tmp_path / "does-not-exist"))
    with pytest.raises(config_mod.ConfigError):
        config_mod.load()


def test_config_load_fails_when_salt_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    salt = tmp_path / "salt"
    salt.write_text("   \n\n", encoding="utf-8")
    monkeypatch.setenv("SHERPA_SALT_PATH", str(salt))
    with pytest.raises(config_mod.ConfigError):
        config_mod.load()
