"""Agent abstraction: schema, selection registry, adapter argv/parse, sandbox."""

from __future__ import annotations

import pytest

import sherpa.agent as agent
from sherpa.agent import sandbox
from sherpa.agent.adapters import claude, codex
from sherpa.agent.schema import (
    Finding,
    extract_json_object,
    parse_review_result,
    result_to_dict,
)


# ---- schema ----

def test_finding_rejects_non_severity_language():
    # severity must never be an approval-style signal
    with pytest.raises(ValueError):
        Finding(file="a.py", line_start=1, line_end=1, severity="approved", body="x")


def test_parse_review_result_from_dict():
    data = {
        "summary": "  map  ",
        "findings": [
            {"file": "a.py", "line_start": 1, "line_end": 3, "severity": "nit", "body": "b"}
        ],
        "category_evidence": {"changed_files": ["a.py"]},
        "open_questions": ["why?"],
    }
    r = parse_review_result(data)
    assert r.summary == "map"
    assert r.findings[0].file == "a.py" and r.findings[0].severity == "nit"
    assert r.category_evidence == {"changed_files": ["a.py"]}
    assert r.open_questions == ("why?",)
    # roundtrips structurally
    assert result_to_dict(r)["findings"][0]["line_end"] == 3


def test_parse_review_result_rejects_bad_severity():
    with pytest.raises(ValueError):
        parse_review_result({"summary": "x", "findings": [{"file": "a", "severity": "lgtm"}]})


def test_extract_json_object_embedded_in_prose():
    text = 'Here is my review:\n{"summary": "ok", "findings": []}\nThanks!'
    assert extract_json_object(text)["summary"] == "ok"


def test_extract_json_object_none_raises():
    with pytest.raises(ValueError):
        extract_json_object("no json here")


# ---- selection ----

def test_builtin_agents_registered():
    assert {"claude", "codex", "ollama"}.issubset(set(agent.available()))


def test_select_unknown_raises():
    with pytest.raises(ValueError):
        agent.select("does-not-exist")


def test_resolve_default_and_override():
    assert agent.resolve("claude").name == "claude"
    assert agent.resolve("claude", "codex").name == "codex"


# ---- adapter argv / sandbox policy ----

def test_claude_argv_is_read_only_and_structured():
    argv = claude._build_argv(None)
    assert "-p" in argv and "json" in argv
    allowed = argv[argv.index("--allowedTools") + 1]
    assert "Read" in allowed
    assert "Write" not in allowed and "Edit" not in allowed
    assert sandbox.CLAUDE_ALLOWED_TOOLS == ("Read", "Grep", "Glob")


def test_codex_argv_uses_read_only_sandbox():
    argv = codex._build_argv("gpt-x")
    assert argv[:2] == ["codex", "exec"]
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert argv[argv.index("--model") + 1] == "gpt-x"


def test_claude_parse_envelope_and_trajectory():
    stdout = (
        '{"type":"result","result":"{\\"summary\\":\\"hi\\",\\"findings\\":'
        '[{\\"file\\":\\"a.py\\",\\"line_start\\":1,\\"line_end\\":2,'
        '\\"severity\\":\\"nit\\",\\"body\\":\\"x\\"}]}",'
        '"model":"claude-x","session_id":"sess1"}'
    )
    result, traj = claude._parse(stdout)
    assert result.summary == "hi"
    assert result.findings[0].file == "a.py"
    assert traj.agent_name == "claude"
    assert traj.model_id == "claude-x"
    assert traj.raw_session_ref == "sess1"
