# hotdocs-criterion: sha256:6216fb583c5a09e75b801cc3392eac987c219b1315270369ae0aeec6ff70ab33
import json
import os
from pathlib import Path

import pytest

import llm_endpoint


MODEL = "anthropic:claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _call_files(cwd: Path):
    calls_dir = cwd / ".hotdocs" / "calls"
    if not calls_dir.is_dir():
        return []
    return sorted(p for p in calls_dir.rglob("*") if p.is_file())


def _timeout_backend(prompt, model, **params):
    raise TimeoutError("timed out")


def _ok_backend(prompt, model, **params):
    return {
        "text": "hello from the mock",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def test_ac_endpoint_006_calls_log_has_one_timeout_and_one_success_record(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    assert _call_files(tmp_path) == []

    # First, independent call: fails with a timeout.
    failed = llm_endpoint.complete("first prompt", MODEL, backend=_timeout_backend)
    err = field(failed, "model_call_error")
    assert err is not None
    assert field(err, "category") == "timeout"
    # The record is written before complete() returns.
    assert len(_call_files(tmp_path)) == 1

    # Second, independent call: succeeds.
    ok = llm_endpoint.complete("second prompt", MODEL, backend=_ok_backend)
    assert field(ok, "model_call_error") is None
    assert len(_call_files(tmp_path)) == 2

    files = _call_files(tmp_path)
    assert len(files) == 2

    # Each record is plain JSON: no bespoke parsing needed.
    records = [json.loads(p.read_text(encoding="utf-8")) for p in files]
    assert all(isinstance(r, dict) for r in records)

    errored = [r for r in records if r.get("model_call_error") is not None]
    clean = [r for r in records if r.get("model_call_error") is None]
    assert len(errored) == 1
    assert len(clean) == 1
    assert errored[0]["model_call_error"]["category"] == "timeout"
    for r in records:
        assert r.get("model") == MODEL
        assert "timestamp" in r
        assert "backend" in r

    # Queryable via DuckDB's read_json, when DuckDB is available.
    try:
        import duckdb  # noqa: F401
    except ImportError:
        return

    file_list = "[" + ", ".join(_sql_str(str(p)) for p in files) + "]"
    con = duckdb.connect()
    try:
        total = con.execute(
            f"SELECT count(*) FROM read_json({file_list}, union_by_name=true)"
        ).fetchone()[0]
        assert total == 2

        rows = con.execute(
            "SELECT model_call_error.category "
            f"FROM read_json({file_list}, union_by_name=true) "
            "WHERE model_call_error IS NOT NULL"
        ).fetchall()
        assert rows == [("timeout",)]

        no_error = con.execute(
            f"SELECT count(*) FROM read_json({file_list}, union_by_name=true) "
            "WHERE model_call_error IS NULL"
        ).fetchone()[0]
        assert no_error == 1
    finally:
        con.close()