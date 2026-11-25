# hotdocs-criterion: sha256:ba69d3ce82f5810874de1cc20ff97f6b7178532eef97bc671da0a994f1a1d40c
"""AC-TRACK-007: a failed generation (model_call_error populated, no
VerificationReport) still writes exactly one AttemptRecord under
.hotdocs/attempts/<component_id>/, with generation populated,
verification null, queryable via DuckDB's read_json with no bespoke
parsing."""

import dataclasses
import json
from pathlib import Path

import pytest

import provenance_tracker


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeGenerationResult:
    component_id: str
    model: str
    prompt_version: str
    files: list
    model_call_error: dict
    tags: set


def _failed_generation():
    return FakeGenerationResult(
        component_id=COMPONENT_ID,
        model="anthropic:claude-sonnet-5",
        prompt_version="v11",
        files=[],
        model_call_error={"category": "network", "message": "connection refused"},
        tags={"b", "a"},
    )


def _write(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID,
        _failed_generation(),
        None,
        SPEC_BUNDLE_HASH,
        repo_root,
    )
    attempts_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    assert attempts_dir.is_dir(), "attempts directory was not created"
    files = [p for p in attempts_dir.iterdir() if p.is_file()]
    assert len(files) == 1, "expected exactly one AttemptRecord file, got " + repr(files)
    return repo_root, record, files[0]


def test_failed_generation_writes_one_record_with_null_verification(tmp_path):
    repo_root, record, path = _write(tmp_path)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert "attempt_id" in on_disk and on_disk["attempt_id"]
    assert "timestamp" in on_disk and on_disk["timestamp"]

    # verification is null: generation itself failed
    assert "verification" in on_disk
    assert on_disk["verification"] is None

    # generation is populated, in plain JSON form
    gen = on_disk["generation"]
    assert isinstance(gen, dict)
    assert gen["model_call_error"] == {
        "category": "network",
        "message": "connection refused",
    }
    assert gen["component_id"] == COMPONENT_ID
    assert gen["model"] == "anthropic:claude-sonnet-5"
    assert gen["prompt_version"] == "v11"
    assert gen["files"] == []
    assert gen["tags"] == ["a", "b"]

    # The returned record carries the same plain form, not the original object
    rec_gen = field(record, "generation")
    assert not isinstance(rec_gen, FakeGenerationResult)
    assert isinstance(rec_gen, dict)
    assert rec_gen == gen
    assert field(record, "verification") is None
    assert field(record, "component_id") == COMPONENT_ID


def test_record_queryable_with_duckdb_read_json(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    _repo_root, _record, path = _write(tmp_path)

    literal = "'" + str(path).replace("'", "''") + "'"
    con = duckdb.connect()
    try:
        cur = con.execute("SELECT * FROM read_json(" + literal + ")")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    finally:
        con.close()

    assert len(rows) == 1
    row = dict(zip(cols, rows[0]))
    assert row["component_id"] == COMPONENT_ID
    assert row["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert "verification" in row
    assert row["verification"] is None

    gen = row["generation"]
    if isinstance(gen, str):
        gen = json.loads(gen)
    assert gen is not None
    mce = gen["model_call_error"]
    if isinstance(mce, str):
        mce = json.loads(mce)
    assert mce["message"] == "connection refused"
    assert mce["category"] == "network"