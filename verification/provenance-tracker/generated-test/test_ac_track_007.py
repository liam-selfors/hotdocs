import json
import tempfile
from pathlib import Path

import duckdb

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_write_attempt_record_generation_failure_has_no_verification():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        component_id = "comp-foo"
        spec_bundle_hash = "sha256:" + "a" * 64

        generation_result = {
            "component_id": component_id,
            "model": "gpt-5",
            "seed": 0,
            "candidate_files": [],
            "model_call_error": {
                "category": "timeout",
                "message": "model call timed out after 120s",
            },
        }

        record = provenance_tracker.write_attempt_record(
            component_id,
            generation_result,
            None,
            spec_bundle_hash,
            repo_root,
        )

        generation_field = _get(record, "generation")
        verification_field = _get(record, "verification")

        assert verification_field is None
        assert isinstance(generation_field, dict)
        model_call_error_field = _get(generation_field, "model_call_error")
        assert isinstance(model_call_error_field, dict)
        assert _get(model_call_error_field, "category") == "timeout"
        assert _get(model_call_error_field, "message") == "model call timed out after 120s"

        attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
        assert attempts_dir.is_dir()

        written_files = sorted(p for p in attempts_dir.glob("*") if p.is_file())
        assert len(written_files) == 1
        attempt_file = written_files[0]

        with open(attempt_file, "r", encoding="utf-8") as f:
            on_disk = json.load(f)

        assert on_disk["component_id"] == component_id
        assert on_disk["spec_bundle_hash"] == spec_bundle_hash
        assert on_disk["verification"] is None
        assert isinstance(on_disk["generation"], dict)
        assert on_disk["generation"]["model_call_error"]["category"] == "timeout"
        assert on_disk["generation"]["model_call_error"]["message"] == (
            "model call timed out after 120s"
        )

        rows = duckdb.sql(
            "SELECT component_id, spec_bundle_hash, verification, generation "
            f"FROM read_json('{attempt_file.as_posix()}')"
        ).fetchall()

        assert len(rows) == 1
        (
            queried_component_id,
            queried_spec_bundle_hash,
            queried_verification,
            queried_generation,
        ) = rows[0]

        assert queried_component_id == component_id
        assert queried_spec_bundle_hash == spec_bundle_hash
        assert queried_verification is None
        assert queried_generation is not None
        assert queried_generation["model_call_error"]["category"] == "timeout"
        assert queried_generation["model_call_error"]["message"] == (
            "model call timed out after 120s"
        )