import dataclasses
import json

import duckdb

import provenance_tracker


def _read(obj, key):
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def test_write_attempt_record_generation_failure_only(tmp_path):
    @dataclasses.dataclass
    class FakeGenerationResult:
        model_call_error: dict
        file: object = None

    generation_result = FakeGenerationResult(
        model_call_error={"message": "model endpoint timed out", "category": "timeout"},
        file=None,
    )

    component_id = "comp-widget-maker"
    spec_bundle_hash = "sha256:" + "a" * 64
    repo_root = tmp_path

    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, None, spec_bundle_hash, repo_root
    )

    assert _read(record, "component_id") == component_id
    assert _read(record, "verification") is None
    assert _read(record, "spec_bundle_hash") == spec_bundle_hash

    generation_out = _read(record, "generation")
    assert generation_out is not None
    assert not dataclasses.is_dataclass(generation_out)

    model_call_error_out = _read(generation_out, "model_call_error")
    assert model_call_error_out == {"message": "model endpoint timed out", "category": "timeout"}

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir()

    written_files = list(attempts_dir.iterdir())
    assert len(written_files) == 1
    attempt_file = written_files[0]

    with open(attempt_file) as f:
        on_disk = json.load(f)

    assert on_disk["component_id"] == component_id
    assert on_disk["spec_bundle_hash"] == spec_bundle_hash
    assert on_disk["verification"] is None
    assert "attempt_id" in on_disk
    assert "timestamp" in on_disk
    assert on_disk["generation"]["model_call_error"] == {
        "message": "model endpoint timed out",
        "category": "timeout",
    }

    quoted_path = str(attempt_file).replace("'", "''")
    con = duckdb.connect()
    try:
        count_row = con.execute(
            f"SELECT count(*) FROM read_json('{quoted_path}')"
        ).fetchone()
        assert count_row[0] == 1

        row = con.execute(
            f"SELECT component_id, "
            f"verification IS NULL AS verification_is_null, "
            f"generation IS NOT NULL AS generation_is_not_null, "
            f"generation['model_call_error'] IS NOT NULL AS model_call_error_present "
            f"FROM read_json('{quoted_path}')"
        ).fetchone()
    finally:
        con.close()

    assert row is not None
    queried_component_id, verification_is_null, generation_is_not_null, model_call_error_present = row
    assert queried_component_id == component_id
    assert verification_is_null is True
    assert generation_is_not_null is True
    assert model_call_error_present is True