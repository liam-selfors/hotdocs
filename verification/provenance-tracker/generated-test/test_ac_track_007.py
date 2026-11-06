import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pytest

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class ModelCallError:
    category: str
    message: str


@dataclass
class GenerationResult:
    component_id: str
    model_call_error: ModelCallError | None
    candidate: str | None
    retries: int


def test_write_attempt_record_generation_failure_no_verification(tmp_path: Path):
    repo_root = tmp_path
    component_id = "comp-foo"
    spec_bundle_hash = "sha256:" + "a" * 64

    generation_result = GenerationResult(
        component_id=component_id,
        model_call_error=ModelCallError(category="network", message="timeout"),
        candidate=None,
        retries=2,
    )

    before = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, None, spec_bundle_hash, repo_root
    )
    after = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    attempts_dir = repo_root / ".hotdocs" / "attempts" / component_id
    assert attempts_dir.is_dir()

    written_files = list(attempts_dir.iterdir())
    assert len(written_files) == 1
    attempt_file = written_files[0]

    file_data = json.loads(attempt_file.read_text())

    assert file_data["component_id"] == component_id
    assert file_data["spec_bundle_hash"] == spec_bundle_hash
    assert before <= file_data["timestamp"] <= after
    assert file_data["verification"] is None

    generation_written = file_data["generation"]
    assert generation_written["component_id"] == component_id
    assert generation_written["candidate"] is None
    assert generation_written["retries"] == 2
    assert generation_written["model_call_error"] == {
        "category": "network",
        "message": "timeout",
    }

    attempt_id = file_data["attempt_id"]
    assert isinstance(attempt_id, str) and len(attempt_id) > 0
    assert attempt_file.name.startswith(attempt_id)

    record_generation = _get(record, "generation")
    record_verification = _get(record, "verification")
    record_component_id = _get(record, "component_id")
    record_spec_bundle_hash = _get(record, "spec_bundle_hash")
    record_timestamp = _get(record, "timestamp")
    record_attempt_id = _get(record, "attempt_id")

    assert record_component_id == component_id
    assert record_spec_bundle_hash == spec_bundle_hash
    assert record_timestamp == file_data["timestamp"]
    assert record_attempt_id == attempt_id
    assert record_verification is None

    assert record_generation == generation_written
    assert record_generation is not generation_result
    assert not isinstance(record_generation, GenerationResult)

    generation_result.retries = 999
    assert _get(record, "generation")["retries"] == 2

    rel = duckdb.read_json(str(attempt_file))
    columns = rel.columns
    for expected_col in (
        "attempt_id",
        "component_id",
        "timestamp",
        "spec_bundle_hash",
        "generation",
        "verification",
    ):
        assert expected_col in columns

    rows = rel.fetchall()
    assert len(rows) == 1
    row = dict(zip(columns, rows[0]))

    assert row["component_id"] == component_id
    assert row["spec_bundle_hash"] == spec_bundle_hash
    assert row["verification"] is None

    duck_generation = row["generation"]
    assert duck_generation["retries"] == 2
    assert duck_generation["candidate"] is None
    assert duck_generation["model_call_error"]["category"] == "network"
    assert duck_generation["model_call_error"]["message"] == "timeout"