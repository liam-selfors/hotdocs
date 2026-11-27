# hotdocs-criterion: sha256:5213750846ac5c47f4ed51a1209321d0cf4e4e3013d868f18c013c93397105b3
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:0123456789abcdef"


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v11",
        "files": [],
        "model_call_error": {"category": "network", "message": "connection refused"},
    }


def test_ac_track_007_failed_generation_writes_record_with_null_verification(tmp_path):
    repo_root = tmp_path
    generation = _generation_result()

    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID,
        generation,
        None,
        SPEC_BUNDLE_HASH,
        repo_root,
    )

    # Exactly one AttemptRecord file under .hotdocs/attempts/<component_id>/
    attempts_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    assert attempts_dir.is_dir()
    files = [p for p in attempts_dir.iterdir() if p.is_file()]
    assert len(files) == 1, files
    record_path = files[0]

    # On-disk content: generation populated, verification null
    on_disk = json.loads(record_path.read_text(encoding="utf-8"))
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert on_disk["verification"] is None
    assert isinstance(on_disk["generation"], dict)
    assert on_disk["generation"]["model_call_error"] == generation["model_call_error"]
    assert on_disk["generation"]["component_id"] == COMPONENT_ID

    # Returned record mirrors the plain form written to disk
    assert field(record, "verification") is None
    returned_generation = field(record, "generation")
    assert isinstance(returned_generation, dict)
    assert returned_generation == on_disk["generation"]

    # Queryable via DuckDB's read_json with no bespoke parsing
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    path_literal = "'" + str(record_path).replace("'", "''") + "'"
    rows = con.execute(
        "SELECT component_id, spec_bundle_hash, generation IS NOT NULL, "
        "verification IS NULL FROM read_json(" + path_literal + ")"
    ).fetchall()
    assert len(rows) == 1
    component_id, bundle_hash, has_generation, verification_is_null = rows[0]
    assert component_id == COMPONENT_ID
    assert bundle_hash == SPEC_BUNDLE_HASH
    assert has_generation is True
    assert verification_is_null is True
    con.close()