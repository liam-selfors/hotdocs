# hotdocs-criterion: sha256:5e1533bbfe0e43f77a02a5d5a04e246dada08c6ca40a3bc4e8a8112edd7b5650
import json
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _mock_backend(prompt, model, **params):
    if prompt == "first-call-times-out":
        raise TimeoutError("timed out")
    return {
        "text": "hello back",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def _record_files(workdir):
    calls_dir = workdir / ".hotdocs" / "calls"
    assert calls_dir.is_dir(), "expected .hotdocs/calls/ to exist after complete()"
    return sorted(p for p in calls_dir.iterdir() if p.is_file())


def test_ac_endpoint_006_two_calls_two_records_queryable(workdir):
    model = "anthropic:claude-sonnet-5"

    failed = llm_endpoint.complete("first-call-times-out", model, backend=_mock_backend)
    succeeded = llm_endpoint.complete("second-call-succeeds", model, backend=_mock_backend)

    # Sanity on the returned responses themselves.
    failed_error = field(failed, "model_call_error")
    assert failed_error is not None
    assert field(failed_error, "category") == "timeout"
    assert field(failed, "text") is None
    assert field(succeeded, "model_call_error") is None
    assert field(succeeded, "text") == "hello back"

    files = _record_files(workdir)
    assert len(files) == 2, "expected exactly two call records, got: " + repr(
        [p.name for p in files]
    )

    # Plain JSON view of the records.
    records = [json.loads(p.read_text()) for p in files]
    for rec in records:
        assert isinstance(rec, dict)
        assert rec.get("timestamp")
        assert rec.get("model") == model
        assert rec.get("backend")

    with_error = [r for r in records if r.get("model_call_error") is not None]
    without_error = [r for r in records if r.get("model_call_error") is None]
    assert len(with_error) == 1
    assert len(without_error) == 1
    assert with_error[0]["model_call_error"]["category"] == "timeout"
    assert "model_call_error" not in without_error[0] or without_error[0]["model_call_error"] is None
    assert without_error[0].get("text_present") is True

    # Queryable via DuckDB's read_json, with no bespoke parsing.
    duckdb = pytest.importorskip("duckdb")
    glob = str(workdir / ".hotdocs" / "calls" / "*")
    con = duckdb.connect()
    total = con.execute(
        "SELECT count(*) FROM read_json(?, union_by_name = true)", [glob]
    ).fetchone()[0]
    assert total == 2

    rows = con.execute(
        "SELECT model, model_call_error.category AS category "
        "FROM read_json(?, union_by_name = true)",
        [glob],
    ).fetchall()
    categories = sorted([r[1] for r in rows], key=lambda c: (c is not None, c))
    assert categories == [None, "timeout"]
    assert all(r[0] == model for r in rows)