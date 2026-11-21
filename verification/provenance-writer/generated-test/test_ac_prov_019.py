# hotdocs-criterion: sha256:6d2c3d2a8e351e332f444d516ac5a582fff1e2b1c6ae11b4492e870255562827
import copy
import json
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4


def valid_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": valid_report(),
    }


EXISTING_MANIFEST = {
    "kind": "sealed-provenance",
    "version": 1,
    "component_id": "comp-foo",
    "owners": ["pipeline-team"],
    "source_path": "pipeline/foo/",
    "source_hash": VALID_HASH,
    "verifier_version": "verifier-orchestrator@1.0.0",
    "characterization": {"overall": "pass", "criteria_passed": 3, "criteria_total": 3},
    "written_at": "2026-01-01T00:00:00Z",
}


def snapshot(root):
    result = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            result[str(p.relative_to(root))] = p.read_bytes()
        else:
            result[str(p.relative_to(root)) + "/"] = None
    return result


def with_change(key, value):
    inputs = valid_inputs()
    inputs[key] = value
    return inputs


def without(key):
    inputs = valid_inputs()
    del inputs[key]
    return inputs


def empty_criteria():
    inputs = valid_inputs()
    inputs["verification_report"]["criteria"] = []
    return inputs


INVALID_CASES = [
    ("source_path_escape", "comp-foo", lambda: with_change("source_path", "../escape/")),
    ("source_path_gen", "comp-foo", lambda: with_change("source_path", "gen/foo/")),
    ("source_path_abs", "comp-foo", lambda: with_change("source_path", "/abs/path/")),
    ("owners_empty", "comp-foo", lambda: with_change("owners", [])),
    ("owner_uppercase", "comp-foo", lambda: with_change("owners", ["Alice"])),
    ("source_hash_short", "comp-foo", lambda: with_change("source_hash", "sha256:abc")),
    ("verifier_version_bad", "comp-foo", lambda: with_change("verifier_version", "v2")),
    ("criteria_empty", "comp-foo", empty_criteria),
    ("component_id_mismatch", "comp-bar", valid_inputs),
    ("source_hash_missing", "comp-foo", lambda: without("source_hash")),
]


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / ".sealed-provenance.json"
    manifest_path.write_bytes(
        (json.dumps(EXISTING_MANIFEST, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return repo_root, manifest_path


def test_valid_inputs_control_does_not_raise(tmp_path):
    repo_root, _ = make_repo(tmp_path)
    provenance_writer.write_sealed_provenance("comp-foo", valid_inputs(), repo_root)


@pytest.mark.parametrize(
    "case_id,component_id,build",
    INVALID_CASES,
    ids=[c[0] for c in INVALID_CASES],
)
def test_invalid_sealed_input_raises_and_leaves_manifest(tmp_path, case_id, component_id, build):
    repo_root, manifest_path = make_repo(tmp_path)
    before_bytes = manifest_path.read_bytes()
    before_tree = snapshot(tmp_path)

    inputs = build()
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)

    assert manifest_path.read_bytes() == before_bytes
    assert snapshot(tmp_path) == before_tree


def test_overall_pass_with_failed_criterion_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = valid_inputs()
    report = copy.deepcopy(inputs["verification_report"])
    report["overall"] = "pass"
    report["criteria"][1]["result"] = "fail"
    report["requirement_results"]["R-FOO-002"] = "fail"
    inputs["verification_report"] = report

    before_tree = snapshot(tmp_path)

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").exists()
    assert snapshot(tmp_path) == before_tree