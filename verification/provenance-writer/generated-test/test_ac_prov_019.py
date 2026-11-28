# hotdocs-criterion: sha256:d94508851cf77ef5befce1cf18618e4f80bd41bb8a795e01157b415ae4bba514
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
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
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


def existing_manifest_bytes():
    doc = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "f" * 64,
        "verifier_version": "verifier-orchestrator@1.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 3, "criteria_total": 3},
        "written_at": "2026-01-01T00:00:00Z",
    }
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def snapshot(root):
    root = Path(root)
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _with(key, value):
    def build():
        inputs = valid_inputs()
        inputs[key] = value
        return "comp-foo", inputs
    return build


def _empty_criteria():
    inputs = valid_inputs()
    inputs["verification_report"]["criteria"] = []
    return "comp-foo", inputs


def _mismatched_component_id():
    return "comp-bar", valid_inputs()


def _missing_source_hash():
    inputs = valid_inputs()
    del inputs["source_hash"]
    return "comp-foo", inputs


CASES = {
    "source_path_escape": _with("source_path", "../escape/"),
    "source_path_gen": _with("source_path", "gen/foo/"),
    "source_path_absolute": _with("source_path", "/abs/path/"),
    "owners_empty": _with("owners", []),
    "owner_uppercase": _with("owners", ["Alice"]),
    "source_hash_short": _with("source_hash", "sha256:abc"),
    "verifier_version_bad": _with("verifier_version", "v2"),
    "report_empty_criteria": _empty_criteria,
    "component_id_mismatch": _mismatched_component_id,
    "source_hash_missing": _missing_source_hash,
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_invalid_input_raises_and_leaves_existing_manifest_untouched(tmp_path, case):
    repo_root = tmp_path / "repo"
    manifest = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    manifest.parent.mkdir(parents=True)
    original = existing_manifest_bytes()
    manifest.write_bytes(original)
    before = snapshot(repo_root)

    component_id, inputs = CASES[case]()

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)

    assert manifest.read_bytes() == original
    assert snapshot(repo_root) == before
    assert not (repo_root / "gen").exists()
    assert not (tmp_path / "escape").exists()


def test_pass_overall_with_failing_entry_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    inputs = valid_inputs()
    report = copy.deepcopy(inputs["verification_report"])
    report["criteria"][1]["result"] = "fail"
    report["overall"] = "pass"
    inputs["verification_report"] = report

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").exists()
    assert snapshot(repo_root) == {}