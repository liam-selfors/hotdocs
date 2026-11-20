# hotdocs-criterion: sha256:c0e553b91c3281ab404e81bbed63c513fc4536a98f5797e440eada31e62c5d7b
import copy
import json
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4


def _report(criteria=None, overall="pass"):
    if criteria is None:
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ]
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {c["covers"]: c["result"] for c in criteria},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": _report(),
    }


EXISTING_MANIFEST = {
    "kind": "sealed-provenance",
    "version": 1,
    "component_id": "comp-foo",
    "owners": ["pipeline-team"],
    "source_path": "pipeline/foo/",
    "source_hash": VALID_HASH,
    "verifier_version": "verifier-orchestrator@1.0.0",
    "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
    "written_at": "2026-01-01T00:00:00Z",
}


def _all_files(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file())


def _with(field, value):
    def make():
        inputs = _valid_inputs()
        inputs[field] = value
        return "comp-foo", inputs
    return make


def _without(field):
    def make():
        inputs = _valid_inputs()
        del inputs[field]
        return "comp-foo", inputs
    return make


def _mismatched_id():
    return "comp-bar", _valid_inputs()


BAD_CASES = [
    ("source_path_escape", _with("source_path", "../escape/")),
    ("source_path_gen", _with("source_path", "gen/foo/")),
    ("source_path_absolute", _with("source_path", "/abs/path/")),
    ("owners_empty", _with("owners", [])),
    ("owner_uppercase", _with("owners", ["Alice"])),
    ("source_hash_short", _with("source_hash", "sha256:abc")),
    ("verifier_version_bad", _with("verifier_version", "v2")),
    ("report_no_criteria", _with("verification_report", _report(criteria=[]))),
    ("component_id_mismatch", _mismatched_id),
    ("source_hash_missing", _without("source_hash")),
]


def test_valid_inputs_baseline_writes_manifest(tmp_path):
    # Sanity check: the same inputs, unmodified, are accepted, so each
    # rejection below is due to the one field that was made bad.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    provenance_writer.write_sealed_provenance("comp-foo", _valid_inputs(), repo_root)
    manifest_path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["component_id"] == "comp-foo"


@pytest.mark.parametrize("make", [c[1] for c in BAD_CASES], ids=[c[0] for c in BAD_CASES])
def test_invalid_sealed_input_raises_and_leaves_existing_manifest(tmp_path, make):
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / ".sealed-provenance.json"
    original_bytes = (json.dumps(EXISTING_MANIFEST, indent=2) + "\n").encode("utf-8")
    manifest_path.write_bytes(original_bytes)
    files_before = _all_files(repo_root)

    component_id, inputs = make()
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, copy.deepcopy(inputs), repo_root)

    assert manifest_path.read_bytes() == original_bytes
    assert _all_files(repo_root) == files_before
    assert not (tmp_path / "escape").exists()


def test_overall_pass_with_failed_criterion_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    criteria = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "fail"},
    ]
    inputs = _valid_inputs()
    inputs["verification_report"] = _report(criteria=criteria, overall="pass")

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").exists()
    assert _all_files(repo_root) == []