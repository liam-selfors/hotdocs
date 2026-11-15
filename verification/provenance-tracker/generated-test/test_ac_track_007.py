"""AC-TRACK-007: a failed generation (model_call_error populated, no
VerificationReport) still writes one AttemptRecord under
.hotdocs/attempts/<component_id>/, with generation populated and
verification null, queryable as plain JSON (DuckDB read_json)."""

import dataclasses
import json
from pathlib import Path
from typing import Any, Optional

import provenance_tracker


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:0123456789abcdef"


@dataclasses.dataclass
class GenerationResult:
    component_id: str
    model: str
    seed: int
    candidate: Optional[Any]
    model_call_error: Optional[dict]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_failed_generation():
    return GenerationResult(
        component_id=COMPONENT_ID,
        model="anthropic:claude-sonnet-5",
        seed=0,
        candidate=None,
        model_call_error={"category": "network", "message": "connection refused"},
    )


def _parse_record_file(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Newline-delimited JSON is also natively readable by read_json;
        # it must still hold exactly one record.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert len(lines) == 1, f"expected one JSON record, got {len(lines)} lines"
        return json.loads(lines[0])


def test_failed_generation_writes_attempt_record_with_null_verification(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    generation = _make_failed_generation()
    expected_generation = dataclasses.asdict(generation)

    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID,
        generation,
        None,
        SPEC_BUNDLE_HASH,
        repo_root,
    )

    # --- exactly one file written under .hotdocs/attempts/<component_id>/
    attempts_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    assert attempts_dir.is_dir(), f"{attempts_dir} was not created"
    files = [p for p in attempts_dir.iterdir() if p.is_file()]
    assert len(files) == 1, f"expected exactly one AttemptRecord file, got {files}"
    record_path = files[0]

    # --- on-disk content: plain JSON, generation populated, verification null
    on_disk = _parse_record_file(record_path)
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert on_disk["verification"] is None
    assert on_disk["generation"] is not None
    assert on_disk["generation"] == expected_generation
    assert on_disk["generation"]["model_call_error"] == {
        "category": "network",
        "message": "connection refused",
    }
    assert isinstance(on_disk.get("attempt_id"), str) and on_disk["attempt_id"]
    assert isinstance(on_disk.get("timestamp"), str) and on_disk["timestamp"]
    assert record_path.name.startswith(on_disk["attempt_id"])

    # --- returned record mirrors what was written, in plain form
    returned_generation = field(record, "generation")
    returned_verification = field(record, "verification")
    assert returned_verification is None
    assert returned_generation is not generation
    assert not isinstance(returned_generation, GenerationResult)
    assert isinstance(returned_generation, dict)
    assert returned_generation == expected_generation
    assert field(record, "component_id") == COMPONENT_ID

    # --- queryable by DuckDB's read_json with no bespoke parsing
    try:
        import duckdb  # noqa: F401
    except ImportError:
        duckdb = None
    if duckdb is not None:
        path_literal = str(record_path).replace("'", "''")
        con = duckdb.connect()
        try:
            rows = con.execute(
                "SELECT component_id, spec_bundle_hash, verification IS NULL "
                f"FROM read_json('{path_literal}')"
            ).fetchall()
        finally:
            con.close()
        assert len(rows) == 1
        component_id, bundle_hash, verification_is_null = rows[0]
        assert component_id == COMPONENT_ID
        assert bundle_hash == SPEC_BUNDLE_HASH
        assert verification_is_null is True