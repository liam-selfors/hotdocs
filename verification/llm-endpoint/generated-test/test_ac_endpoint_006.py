# hotdocs-criterion: sha256:6216fb583c5a09e75b801cc3392eac987c219b1315270369ae0aeec6ff70ab33
import json
from pathlib import Path

import pytest

import llm_endpoint


MODEL = "anthropic:claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_backend(log_path):
    state = {"n": 0}

    def mock_backend(prompt, model, **params):
        state["n"] += 1
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call " + str(state["n"]) + "\n")
        if state["n"] == 1:
            raise TimeoutError("simulated timeout")
        return {
            "text": "hello from mock",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return mock_backend


def _call_records(tmp_path):
    calls_dir = tmp_path / ".hotdocs" / "calls"
    assert calls_dir.is_dir(), ".hotdocs/calls/ was not created"
    files = sorted(p for p in calls_dir.rglob("*") if p.is_file())
    return files


def _run_two_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "backend_calls.log"
    backend = _make_backend(log_path)

    first = llm_endpoint.complete("first prompt", MODEL, backend=backend)
    second = llm_endpoint.complete("second prompt", MODEL, backend=backend)

    assert log_path.read_text(encoding="utf-8").splitlines() == ["call 1", "call 2"]
    return first, second


def test_two_calls_write_two_records_one_timeout_one_success(tmp_path, monkeypatch):
    first, second = _run_two_calls(tmp_path, monkeypatch)

    first_err = field(first, "model_call_error")
    assert first_err is not None
    assert field(first_err, "category") == "timeout"
    assert field(first, "text") is None

    assert field(second, "model_call_error") is None
    assert field(second, "text") == "hello from mock"

    files = _call_records(tmp_path)
    assert len(files) == 2, "expected exactly two call records, got " + repr(files)

    records = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for rec in records:
        assert isinstance(rec, dict)
        assert "timestamp" in rec
        assert rec.get("model") == MODEL
        assert "backend" in rec

    errored = [r for r in records if r.get("model_call_error") is not None]
    clean = [r for r in records if r.get("model_call_error") is None]
    assert len(errored) == 1
    assert len(clean) == 1
    assert errored[0]["model_call_error"]["category"] == "timeout"
    assert "model_call_error" not in clean[0] or clean[0]["model_call_error"] is None
    assert clean[0].get("text_present") is True
    # Transport-level log: never a copy of the response text.
    assert "hello from mock" not in json.dumps(clean[0])


def test_call_records_queryable_with_duckdb_read_json(tmp_path, monkeypatch):
    duckdb = pytest.importorskip("duckdb")
    _run_two_calls(tmp_path, monkeypatch)

    files = _call_records(tmp_path)
    assert len(files) == 2

    path_list = "[" + ", ".join(
        "'" + str(p).replace("'", "''") + "'" for p in files
    ) + "]"
    sql = (
        "SELECT model_call_error.category AS category FROM read_json("
        + path_list
        + ", union_by_name=true)"
    )
    con = duckdb.connect()
    rows = con.execute(sql).fetchall()
    con.close()

    assert len(rows) == 2
    categories = sorted((r[0] for r in rows), key=lambda v: (v is not None, v))
    assert categories == [None, "timeout"]