import datetime
import json
import os
from pathlib import Path

import pytest

import llm_endpoint


MODEL = "anthropic:claude-sonnet-5"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _timeout_backend(prompt, model, **params):
    raise TimeoutError("simulated timeout from mock backend")


def _success_backend(prompt, model, **params):
    return {
        "text": "hello from mock",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _run_two_calls(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    calls_dir = work / ".hotdocs" / "calls"
    assert not calls_dir.exists() or not any(p.is_file() for p in calls_dir.rglob("*"))

    failed = llm_endpoint.complete("first prompt", MODEL, backend=_timeout_backend)
    succeeded = llm_endpoint.complete("second prompt", MODEL, backend=_success_backend)

    # Records must be on disk by the time complete() has returned.
    assert calls_dir.is_dir(), ".hotdocs/calls/ was not created"
    files = sorted(p for p in calls_dir.rglob("*") if p.is_file())
    return failed, succeeded, files


def _category(err):
    if err is None:
        return None
    if isinstance(err, str):
        try:
            err = json.loads(err)
        except ValueError:
            return None
    return _field(err, "category")


def test_two_calls_write_two_records_one_timeout_one_success(tmp_path, monkeypatch):
    failed, succeeded, files = _run_two_calls(tmp_path, monkeypatch)

    # Sanity on returned values (dual access).
    failed_err = _field(failed, "model_call_error")
    assert failed_err is not None
    assert _category(failed_err) == "timeout"
    assert _field(failed, "text") is None

    assert _field(succeeded, "model_call_error") is None
    assert _field(succeeded, "text") == "hello from mock"

    assert len(files) == 2, f"expected exactly two call records, found {[str(f) for f in files]}"

    records = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
        assert isinstance(rec, dict), f"{f} is not a single JSON object"
        records.append(rec)

    for rec in records:
        assert rec.get("model") == MODEL
        assert isinstance(rec.get("backend"), str) and rec.get("backend")
        ts = rec.get("timestamp")
        assert isinstance(ts, str) and ts
        parsed = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime.datetime)

    timeout_records = [
        r for r in records
        if isinstance(r.get("model_call_error"), dict)
        and r["model_call_error"].get("category") == "timeout"
    ]
    success_records = [r for r in records if r.get("model_call_error") is None]

    assert len(timeout_records) == 1
    assert len(success_records) == 1

    assert success_records[0].get("text_present") is True
    # Transport-level log: never a copy of the response text.
    assert "hello from mock" not in json.dumps(success_records[0])
    assert "message" in timeout_records[0]["model_call_error"]


def test_call_records_queryable_via_duckdb_read_json(tmp_path, monkeypatch):
    duckdb = pytest.importorskip("duckdb")

    _failed, _succeeded, files = _run_two_calls(tmp_path, monkeypatch)
    assert len(files) == 2

    file_list = "[" + ", ".join(
        "'" + str(f).replace("'", "''") + "'" for f in files
    ) + "]"

    con = duckdb.connect()
    try:
        total = con.execute(
            f"SELECT count(*) FROM read_json({file_list}, union_by_name=true)"
        ).fetchone()[0]
        assert total == 2

        rows = con.execute(
            f"SELECT model, backend, timestamp, model_call_error "
            f"FROM read_json({file_list}, union_by_name=true)"
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 2
    categories = []
    for model, backend, timestamp, err in rows:
        assert model == MODEL
        assert backend is not None
        assert timestamp is not None
        categories.append(_category(err))

    assert categories.count("timeout") == 1
    assert categories.count(None) == 1