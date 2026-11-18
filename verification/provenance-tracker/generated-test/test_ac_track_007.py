# hotdocs-criterion: sha256:2dba6bcb9096ceed0ccb0e18deb8238ca7ab9f3ae6dfb6391d7038195c230c8e
import json
from pathlib import Path

import pytest

import provenance_tracker


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:0123456789abcdef"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "model_call_error": {"category": "network", "message": "connection refused"},
        "candidate": None,
        "model": "anthropic:claude-sonnet-5",
        "seed": 0,
    }


def _attempt_files(repo_root):
    attempts = Path(repo_root) / ".hotdocs" / "attempts"
    if not attempts.is_dir():
        return []
    return sorted(p for p in attempts.rglob("*") if p.is_file())


def _run(repo_root):
    generation = _generation_result()
    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID,
        generation,
        None,
        SPEC_BUNDLE_HASH,
        Path(repo_root),
    )
    return generation, record


def _check_location(path, repo_root):
    attempts = Path(repo_root) / ".hotdocs" / "attempts"
    rel = path.relative_to(attempts)
    assert len(rel.parts) == 2, "attempt file must sit directly in the component's directory: " + str(rel)
    assert rel.parts[0] in (COMPONENT_ID, COMPONENT_ID[len("comp-"):]), str(rel)


def test_failed_generation_writes_one_record_with_null_verification(tmp_path):
    generation, record = _run(tmp_path)

    files = _attempt_files(tmp_path)
    assert len(files) == 1, "expected exactly one attempt file, got " + repr(files)
    path = files[0]
    _check_location(path, tmp_path)

    with open(path, "r", encoding="utf-8") as fh:
        on_disk = json.load(fh)

    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert on_disk["verification"] is None
    assert isinstance(on_disk["generation"], dict)
    assert on_disk["generation"]["model_call_error"] == generation["model_call_error"]
    assert on_disk["generation"] == json.loads(json.dumps(generation))
    assert isinstance(on_disk["attempt_id"], str) and on_disk["attempt_id"]
    assert isinstance(on_disk["timestamp"], str) and on_disk["timestamp"]

    # Returned record carries the same plain form, not the input by reference.
    assert field(record, "verification") is None
    returned_generation = field(record, "generation")
    assert returned_generation == on_disk["generation"]
    assert returned_generation is not generation
    assert field(record, "component_id") == COMPONENT_ID


def test_failed_generation_record_is_queryable_with_duckdb_read_json(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    _run(tmp_path)
    files = _attempt_files(tmp_path)
    assert len(files) == 1, "expected exactly one attempt file, got " + repr(files)
    path = files[0]
    _check_location(path, tmp_path)

    literal = "'" + str(path).replace("'", "''") + "'"
    con = duckdb.connect()
    rows = con.execute(
        "SELECT component_id, spec_bundle_hash, "
        "verification IS NULL AS verification_null, "
        "generation IS NOT NULL AS generation_present "
        "FROM read_json(" + literal + ")"
    ).fetchall()

    assert len(rows) == 1
    component_id, spec_bundle_hash, verification_null, generation_present = rows[0]
    assert component_id == COMPONENT_ID
    assert spec_bundle_hash == SPEC_BUNDLE_HASH
    assert verification_null is True
    assert generation_present is True