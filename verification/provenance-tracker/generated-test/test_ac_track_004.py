import json
import re
from pathlib import Path

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_repo_root():
    here = Path(__file__).resolve()
    for ancestor in [here] + list(here.parents):
        candidate = ancestor / "specs" / "components" / "provenance-tracker" / "component.md"
        if candidate.is_file():
            return ancestor
    raise AssertionError(
        "could not locate specs/components/provenance-tracker/component.md "
        "above " + str(here)
    )


def _frontmatter_depends_on(component_md_text):
    match = re.search(r"^---\n(.*?)\n---", component_md_text, re.DOTALL | re.MULTILINE)
    assert match, "component.md has no frontmatter block"
    frontmatter = match.group(1)
    dep_match = re.search(r"^depends_on:\s*\[([^\]]*)\]", frontmatter, re.MULTILINE)
    if not dep_match:
        return []
    raw = dep_match.group(1).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",")]


def _find_written_record(repo_root, attempt_id):
    attempts_dir = repo_root / ".hotdocs" / "attempts"
    if not attempts_dir.is_dir():
        return None
    for json_path in attempts_dir.rglob("*.json"):
        data = json.loads(json_path.read_text())
        if data.get("attempt_id") == attempt_id:
            return data
    return None


def test_write_attempt_record_takes_plain_values_with_verification_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = {
        "model_call_error": None,
        "model": "claude-sonnet-5",
        "seed": 0,
        "candidate_path": "gen/foo/foo.py",
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }
    spec_bundle_hash = "sha256:" + "a" * 64
    component_id = "comp-foo"

    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, verification_report, spec_bundle_hash, repo_root
    )

    assert _get(record, "component_id") == component_id
    assert _get(record, "spec_bundle_hash") == spec_bundle_hash
    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") == verification_report

    attempt_id = _get(record, "attempt_id")
    assert attempt_id

    written = _find_written_record(repo_root, attempt_id)
    assert written is not None, "write_attempt_record did not persist a record to disk"
    assert written["component_id"] == component_id
    assert written["spec_bundle_hash"] == spec_bundle_hash
    assert written["generation"] == generation_result
    assert written["verification"] == verification_report


def test_write_attempt_record_takes_plain_values_with_null_verification(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    generation_result = {
        "model_call_error": {"message": "model unavailable"},
        "model": "claude-sonnet-5",
        "seed": 0,
    }
    spec_bundle_hash = "sha256:" + "b" * 64
    component_id = "comp-bar"

    record = provenance_tracker.write_attempt_record(
        component_id, generation_result, None, spec_bundle_hash, repo_root
    )

    assert _get(record, "component_id") == component_id
    assert _get(record, "spec_bundle_hash") == spec_bundle_hash
    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") is None

    attempt_id = _get(record, "attempt_id")
    written = _find_written_record(repo_root, attempt_id)
    assert written is not None, "write_attempt_record did not persist a record to disk"
    assert written["verification"] is None
    assert written["generation"] == generation_result


def test_write_attempt_record_succeeds_with_no_component_gate_runner_dependency_present(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # gen/component-gate-runner is deliberately absent: write_attempt_record must
    # not need it to produce a record from the plain parameters it was given.
    assert not (repo_root / "gen" / "component-gate-runner").exists()

    generation_result = {"model_call_error": None, "model": "claude-sonnet-5", "seed": 1}
    verification_report = {
        "component_id": "comp-baz",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }

    record = provenance_tracker.write_attempt_record(
        "comp-baz", generation_result, verification_report, "sha256:" + "c" * 64, repo_root
    )

    assert _get(record, "generation") == generation_result
    assert _get(record, "verification") == verification_report
    assert not (repo_root / "gen" / "component-gate-runner").exists()


def test_depends_on_excludes_component_gate_runner():
    repo_root = _find_repo_root()
    component_md = repo_root / "specs" / "components" / "provenance-tracker" / "component.md"
    text = component_md.read_text()
    depends_on = _frontmatter_depends_on(text)
    assert "comp-component-gate-runner" not in depends_on