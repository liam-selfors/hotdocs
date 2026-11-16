"""AC-ENDPOINT-006: every complete() call writes one record to .hotdocs/calls/,
success or failure, queryable via DuckDB's read_json without bespoke parsing."""

import json
import socket
from pathlib import Path

import pytest

import llm_endpoint


MODEL = "anthropic:claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_flaky_backend():
    """A mock backend: the first call fails with a timeout, the second succeeds."""
    state = {"calls": 0}

    def mock_backend(prompt, model, **params):
        state["calls"] += 1
        if state["calls"] == 1:
            raise socket.timeout("timed out")
        return {
            "text": "hello from mock",
            "model": model,
            "backend": "mock_backend",
            "model_call_error": None,
        }

    return mock_backend, state


def _run_two_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    backend, state = _make_flaky_backend()

    first = llm_endpoint.complete("first prompt", MODEL, backend=backend)
    second = llm_endpoint.complete("second prompt", MODEL, backend=backend)

    assert state["calls"] == 2

    # Sanity on the returned responses themselves.
    first_err = field(first, "model_call_error")
    assert first_err is not None
    assert field(first_err, "category") == "timeout"
    assert field(first, "text") is None

    assert field(second, "model_call_error") is None
    assert field(second, "text") == "hello from mock"

    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir(), ".hotdocs/calls/ was not created"
    files = sorted(p for p in calls_dir.rglob("*.json") if p.is_file())
    return calls_dir, files


def test_two_records_one_timeout_one_success(tmp_path, monkeypatch):
    _, files = _run_two_calls(tmp_path, monkeypatch)

    assert len(files) == 2, f"expected exactly two call records, got {files!r}"

    records = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for rec in records:
        assert isinstance(rec, dict)
        assert rec.get("timestamp")
        assert rec.get("model") == MODEL
        assert rec.get("backend")

    failures = [r for r in records if r.get("model_call_error") is not None]
    successes = [r for r in records if r.get("model_call_error") is None]

    assert len(failures) == 1
    assert len(successes) == 1

    assert failures[0]["model_call_error"]["category"] == "timeout"
    assert successes[0].get("text_present") is True
    # A transport-level log: no response text copied into the record.
    assert "hello from mock" not in json.dumps(successes[0])


def test_records_queryable_via_duckdb_read_json(tmp_path, monkeypatch):
    duckdb = pytest.importorskip("duckdb")

    _, files = _run_two_calls(tmp_path, monkeypatch)
    assert len(files) == 2, f"expected exactly two call records, got {files!r}"

    file_list = ", ".join(
        "'" + str(p).replace("'", "''") + "'" for p in files
    )
    con = duckdb.connect()
    rows = con.execute(
        f"SELECT model_call_error.category AS category "
        f"FROM read_json([{file_list}], union_by_name = true)"
    ).fetchall()

    categories = [row[0] for row in rows]
    assert len(categories) == 2
    assert categories.count("timeout") == 1
    assert categories.count(None) == 1