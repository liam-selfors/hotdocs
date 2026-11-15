import dataclasses
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeGenerationResult:
    component_id: str
    model: str
    seed: int
    files: list
    model_call_error: dict


COMPONENT_ID = "comp-widget-maker"
SPEC_BUNDLE_HASH = "sha256:" + "ab12" * 16


def _attempt_files(repo_root: Path):
    base = repo_root / ".hotdocs" / "attempts"
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file())


def test_failed_generation_writes_attempt_record_with_null_verification(tmp_path):
    repo_root = tmp_path
    error = {"category": "network", "message": "connection refused by model endpoint"}
    generation = FakeGenerationResult(
        component_id=COMPONENT_ID,
        model="anthropic:claude-sonnet-5",
        seed=0,
        files=[],
        model_call_error=error,
    )

    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID,
        generation,
        None,
        SPEC_BUNDLE_HASH,
        repo_root,
    )

    # Exactly one AttemptRecord file written under .hotdocs/attempts/<component_id>/
    files = _attempt_files(repo_root)
    assert len(files) == 1, f"expected exactly one attempt record, found {files}"
    written = files[0]
    expected_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    slug_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID[len("comp-"):]
    assert written.parent in (expected_dir, slug_dir), (
        f"attempt record written to unexpected directory {written.parent}"
    )

    # Plain standard JSON, no bespoke parsing needed
    with open(written, "r", encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert on_disk.get("attempt_id")
    assert on_disk.get("timestamp")

    # generation populated (plain JSON form), verification null
    assert "verification" in on_disk
    assert on_disk["verification"] is None
    gen_on_disk = on_disk["generation"]
    assert isinstance(gen_on_disk, dict)
    assert gen_on_disk == dataclasses.asdict(generation)
    assert gen_on_disk["model_call_error"] == error

    # Returned record mirrors what was written, in plain form
    ret_generation = field(record, "generation")
    assert isinstance(ret_generation, dict)
    assert not isinstance(ret_generation, FakeGenerationResult)
    assert ret_generation == gen_on_disk
    assert field(record, "verification") is None
    assert field(record, "component_id") == COMPONENT_ID

    # Queryable via DuckDB's read_json with no bespoke parsing
    try:
        import duckdb  # noqa: F401
    except ImportError:
        duckdb = None
    if duckdb is not None:
        path_literal = str(written).replace("'", "''")
        con = duckdb.connect()
        try:
            try:
                rows = con.execute(
                    f"SELECT component_id, spec_bundle_hash, verification "
                    f"FROM read_json('{path_literal}')"
                ).fetchall()
            except Exception:
                rows = con.execute(
                    f"SELECT component_id, spec_bundle_hash, verification "
                    f"FROM read_json_auto('{path_literal}')"
                ).fetchall()
        finally:
            con.close()
        assert len(rows) == 1
        assert rows[0][0] == COMPONENT_ID
        assert rows[0][1] == SPEC_BUNDLE_HASH
        assert rows[0][2] is None