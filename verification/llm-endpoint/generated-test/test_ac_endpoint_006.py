# hotdocs-criterion: sha256:15bb88927dfbb5832b366c53a940e84c2bfad3b9c060a172852c26130d488dba
import json
from pathlib import Path

import pytest

import llm_endpoint


MODEL = "anthropic:claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _mock_backend(prompt, model, **params):
    if prompt == "fail please":
        raise TimeoutError("timed out")
    return {
        "text": "hello",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _run_two_calls(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    failed = llm_endpoint.complete("fail please", MODEL, backend=_mock_backend)
    succeeded = llm_endpoint.complete("succeed please", MODEL, backend=_mock_backend)
    return failed, succeeded


def _calls_dir(tmp_path):
    return Path(tmp_path) / ".hotdocs" / "calls"


def test_two_call_records_one_timeout_one_success(tmp_path, monkeypatch):
    failed, succeeded = _run_two_calls(tmp_path, monkeypatch)

    # Sanity on the returned responses.
    failed_err = field(failed, "model_call_error")
    assert failed_err is not None
    assert field(failed_err, "category") == "timeout"
    assert field(failed, "text") is None
    assert field(succeeded, "model_call_error") is None
    assert field(succeeded, "text") == "hello"

    calls_dir = _calls_dir(tmp_path)
    assert calls_dir.is_dir()
    files = sorted(p for p in calls_dir.iterdir() if p.is_file())
    assert len(files) == 2, [p.name for p in files]

    records = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    for rec in records:
        assert rec.get("timestamp")
        assert rec.get("model") == MODEL
        assert rec.get("backend")

    errored = [r for r in records if r.get("model_call_error")]
    clean = [r for r in records if not r.get("model_call_error")]
    assert len(errored) == 1
    assert len(clean) == 1
    assert errored[0]["model_call_error"]["category"] == "timeout"
    assert clean[0].get("text_present") is True
    # Transport-level log: the response text itself is not copied.
    assert "hello" not in json.dumps(clean[0])


def test_call_records_queryable_with_duckdb_read_json(tmp_path, monkeypatch):
    _run_two_calls(tmp_path, monkeypatch)
    duckdb = pytest.importorskip("duckdb")

    calls_dir = _calls_dir(tmp_path)
    glob = str(calls_dir / "*")
    con = duckdb.connect()
    total = con.execute(
        "SELECT count(*) FROM read_json(?, union_by_name = true)", [glob]
    ).fetchone()[0]
    assert total == 2

    timeouts = con.execute(
        "SELECT count(*) FROM read_json(?, union_by_name = true) "
        "WHERE model_call_error.category = 'timeout'",
        [glob],
    ).fetchone()[0]
    assert timeouts == 1

    no_error = con.execute(
        "SELECT count(*) FROM read_json(?, union_by_name = true) "
        "WHERE model_call_error IS NULL",
        [glob],
    ).fetchone()[0]
    assert no_error == 1