"""Post-processing invariants for inference output."""

from __future__ import annotations

from sherpa.inference.prompt import PREFIX, postprocess


def test_postprocess_prepends_prefix_when_missing() -> None:
    out = postprocess("issue: variable name unclear")
    assert out.startswith(PREFIX)


def test_postprocess_strips_lgtm_and_approval_phrases() -> None:
    raw = "[pre-flight] LGTM. Looks good to me. Ship it. Approved."
    out = postprocess(raw)
    lowered = out.lower()
    for needle in ("lgtm", "looks good to me", "ship it", "approved", "approve"):
        assert needle not in lowered, f"{needle!r} survived in {out!r}"


def test_postprocess_emits_neutral_placeholder_when_emptied() -> None:
    raw = "LGTM. Approved."
    out = postprocess(raw)
    assert out.startswith(PREFIX)
    assert "approve" not in out.lower()
    assert len(out) > len(PREFIX)


def test_postprocess_keeps_non_approval_content() -> None:
    raw = "[pre-flight] Possible deadlock around mutex M when synced from RT thread."
    out = postprocess(raw)
    assert "deadlock" in out
    assert out.startswith(PREFIX)
