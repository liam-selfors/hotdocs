"""AC-TRACK-007: write_attempt_record on a generation failure (no VerificationReport)."""
import json
import tempfile
from pathlib import Path

import pytest

import provenance_tracker


def field(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


class FakeGenerationResult:
    """Stands in for the real GenerationResult: generation itself failed."""

    def __init__(self):
        self.component_id = "comp-foo"
        self.model = "fake-model-1"
        self.seed = 0
        self.prompt_version = "v1"
        self.candidate = None
        self.cache_hit = False
        self.model_call_error = {
            "category": "timeout",
            "message": "simulated model call timeout",
        }


def test_write_attempt_record_generation_failure_no_verification():
    component_id = "comp-foo"
    spec_bundle_hash = "sha256:" + "a" * 64
    generation_result = FakeGenerationResult()

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        record = provenance_tracker.write_attempt_record(
            component_id,
            generation_result,
            None,
            spec_bundle_hash,
            repo_root,
        )

        # --- the returned AttemptRecord ---
        assert field(record, "component_id") == component_id
        assert field(record, "spec_bundle_hash") == spec_bundle_hash

        returned_generation = field(record, "generation")
        returned_verification = field(record, "verification")

        # Must be the plain JSON-equivalent form (a dict), never the original
        # GenerationResult object echoed back by reference.
        assert isinstance(returned_generation, dict)
        assert returned_generation is not generation_result
        assert returned_generation["model_call_error"] == generation_result.model_call_error

        assert returned_verification is None

        # --- exactly one AttemptRecord file written to disk ---
        attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
        assert attempts_dir.is_dir()
        written_files = list(attempts_dir.glob("*"))
        assert len(written_files) == 1
        attempt_file = written_files[0]

        # Filename is attempt_id-prefixed (chronological glob ordering).
        attempt_id = field(record, "attempt_id")
        assert attempt_file.name.startswith(str(attempt_id))

        # --- the file content itself, read with plain stdlib json (no bespoke parsing) ---
        with open(attempt_file, "r", encoding="utf-8") as f:
            on_disk = json.load(f)

        assert on_disk["component_id"] == component_id
        assert on_disk["spec_bundle_hash"] == spec_bundle_hash
        assert isinstance(on_disk["generation"], dict)
        assert on_disk["generation"]["model_call_error"] == generation_result.model_call_error
        assert on_disk["verification"] is None
        # Consistent with what write_attempt_record returned in memory.
        assert on_disk["generation"] == returned_generation
        assert on_disk["verification"] == returned_verification

        # --- the file is queryable via DuckDB's read_json, with no bespoke parsing ---
        duckdb = pytest.importorskip("duckdb")
        escaped_path = str(attempt_file).replace("'", "''")
        relation = duckdb.sql(f"SELECT * FROM read_json('{escaped_path}')")
        rows = relation.fetchall()
        columns = relation.columns

        assert len(rows) == 1
        assert "generation" in columns
        assert "verification" in columns

        row = rows[0]
        generation_value = row[columns.index("generation")]
        verification_value = row[columns.index("verification")]

        assert generation_value is not None
        assert verification_value is None