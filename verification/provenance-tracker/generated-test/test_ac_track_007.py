import dataclasses
import json
from pathlib import Path

import pytest

import provenance_tracker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeModelCallError:
    category: str
    message: str


@dataclasses.dataclass
class FakeGenerationResult:
    component_id: str
    model: str
    seed: int
    files: list
    model_call_error: object


COMPONENT_ID = "comp-foo"
SPEC_BUNDLE_HASH = "sha256:" + "ab12" * 16


def _attempt_files(repo_root: Path):
    base = repo_root / ".hotdocs" / "attempts"
    if not base.exists():
        return []
    return sorted(p for p in base.rglob("*") if p.is_file())


def _load_json_document(path: Path):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Newline-delimited JSON is also directly readable by read_json.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert len(lines) == 1, "expected exactly one record in the attempt file"
        return json.loads(lines[0])


def test_failed_generation_writes_attempt_record_with_null_verification(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation = FakeGenerationResult(
        component_id=COMPONENT_ID,
        model="anthropic:claude-sonnet-5",
        seed=0,
        files=[],
        model_call_error=FakeModelCallError(
            category="network", message="connection reset by peer"
        ),
    )
    expected_generation = dataclasses.asdict(generation)

    record = provenance_tracker.write_attempt_record(
        COMPONENT_ID, generation, None, SPEC_BUNDLE_HASH, repo_root
    )

    # Exactly one AttemptRecord file written under .hotdocs/attempts/<component_id>/
    files = _attempt_files(repo_root)
    assert len(files) == 1, f"expected exactly one attempt file, found {files}"
    attempt_file = files[0]
    attempts_root = repo_root / ".hotdocs" / "attempts"
    rel_parent = attempt_file.parent.relative_to(attempts_root)
    # The criterion names the directory by component id; accept the bare-slug
    # form too, since the glossary builds paths from the slug.
    assert rel_parent.as_posix() in (COMPONENT_ID, COMPONENT_ID[len("comp-"):]), (
        f"attempt file written under unexpected directory: {rel_parent}"
    )

    # On-disk content: plain JSON, generation populated, verification null.
    on_disk = _load_json_document(attempt_file)
    assert isinstance(on_disk, dict)
    assert on_disk["component_id"] == COMPONENT_ID
    assert on_disk["spec_bundle_hash"] == SPEC_BUNDLE_HASH
    assert "verification" in on_disk
    assert on_disk["verification"] is None
    assert on_disk["generation"] is not None
    assert on_disk["generation"] == expected_generation
    assert on_disk["generation"]["model_call_error"] == {
        "category": "network",
        "message": "connection reset by peer",
    }

    # Returned record mirrors what was written, in plain JSON form.
    returned_generation = field(record, "generation")
    assert returned_generation is not generation
    assert not isinstance(returned_generation, FakeGenerationResult)
    assert returned_generation == on_disk["generation"]
    assert field(record, "verification") is None
    assert field(record, "component_id") == COMPONENT_ID

    # Queryable via DuckDB's read_json with no bespoke parsing.
    try:
        import duckdb  # noqa: F401
    except ImportError:
        duckdb = None

    if duckdb is not None:
        con = duckdb.connect()
        path_literal = str(attempt_file).replace("'", "''")
        rows = con.execute(
            "SELECT component_id, spec_bundle_hash, "
            "verification IS NULL AS verification_is_null, "
            "generation IS NOT NULL AS generation_present "
            f"FROM read_json('{path_literal}')"
        ).fetchall()
        assert len(rows) == 1
        component_id, bundle_hash, verification_is_null, generation_present = rows[0]
        assert component_id == COMPONENT_ID
        assert bundle_hash == SPEC_BUNDLE_HASH
        assert verification_is_null is True
        assert generation_present is True