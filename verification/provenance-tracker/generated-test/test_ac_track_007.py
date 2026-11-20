# hotdocs-criterion: sha256:938c97c7db4d1261f9faac49e37e39107e93d52a083a8627149d9a8be4d11698
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_track_007_failed_generation_writes_queryable_record(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo"

    generation_result = {
        "component_id": component_id,
        "files": [],
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
        "model_call_error": {
            "category": "network",
            "message": "connection refused",
        },
    }

    record = provenance_tracker.write_attempt_record(
        component_id,
        generation_result,
        None,
        "sha256:" + "0" * 64,
        repo_root,
    )

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir(), "attempts directory was not created: " + str(attempts_dir)
    files = sorted(p for p in attempts_dir.iterdir() if p.is_file())
    assert len(files) == 1, "expected exactly one attempt record, found: " + repr(files)
    record_path = files[0]

    on_disk = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == component_id
    assert on_disk["spec_bundle_hash"] == "sha256:" + "0" * 64
    assert record_path.name.startswith(on_disk["attempt_id"])

    gen = on_disk["generation"]
    assert isinstance(gen, dict) and gen, "generation must be populated"
    assert gen["model_call_error"] == {
        "category": "network",
        "message": "connection refused",
    }
    assert "verification" in on_disk
    assert on_disk["verification"] is None

    returned_generation = field(record, "generation")
    returned_verification = field(record, "verification")
    assert isinstance(returned_generation, dict)
    assert returned_generation == gen
    assert returned_verification is None
    assert field(record, "component_id") == component_id

    escaped = str(record_path).replace("'", "''")
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT component_id, generation IS NOT NULL, verification IS NULL "
            "FROM read_json('" + escaped + "')"
        ).fetchall()
    finally:
        con.close()
    assert len(rows) == 1
    assert rows[0][0] == component_id
    assert rows[0][1] is True
    assert rows[0][2] is True