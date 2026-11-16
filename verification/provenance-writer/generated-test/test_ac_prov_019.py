"""AC-PROV-019: write_sealed_provenance validates before writing and never invents.

Covers R-PROV-019.
"""

import copy
import json
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4
VALID_VERIFIER = "verifier-orchestrator@2.0.0"


def _report(criteria=None, overall="pass"):
    if criteria is None:
        criteria = [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ]
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {
            c["covers"]: ("pass" if c["result"] == "pass" else "fail") for c in criteria
        },
        "interface_drift": False,
        "mutation_score": None,
        "overall": overall,
    }


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": VALID_VERIFIER,
        "verification_report": _report(),
    }


def _existing_manifest_bytes():
    doc = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "f" * 64,
        "verifier_version": "verifier-orchestrator@1.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 3, "criteria_total": 3},
        "written_at": "2026-11-02T00:00:00Z",
    }
    return (json.dumps(doc, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _snapshot(root: Path):
    files = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            files[str(p.relative_to(root))] = p.read_bytes()
    return files


def _setup_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest = manifest_dir / ".sealed-provenance.json"
    original = _existing_manifest_bytes()
    manifest.write_bytes(original)
    return repo_root, manifest, original


def _case_source_path_escape():
    inputs = _valid_inputs()
    inputs["source_path"] = "../escape/"
    return "comp-foo", inputs


def _case_source_path_gen():
    inputs = _valid_inputs()
    inputs["source_path"] = "gen/foo/"
    return "comp-foo", inputs


def _case_source_path_abs():
    inputs = _valid_inputs()
    inputs["source_path"] = "/abs/path/"
    return "comp-foo", inputs


def _case_owners_empty():
    inputs = _valid_inputs()
    inputs["owners"] = []
    return "comp-foo", inputs


def _case_owner_uppercase():
    inputs = _valid_inputs()
    inputs["owners"] = ["Alice"]
    return "comp-foo", inputs


def _case_bad_hash():
    inputs = _valid_inputs()
    inputs["source_hash"] = "sha256:abc"
    return "comp-foo", inputs


def _case_bad_verifier_version():
    inputs = _valid_inputs()
    inputs["verifier_version"] = "v2"
    return "comp-foo", inputs


def _case_empty_criteria():
    inputs = _valid_inputs()
    inputs["verification_report"] = _report(criteria=[], overall="pass")
    return "comp-foo", inputs


def _case_component_id_mismatch():
    inputs = _valid_inputs()
    return "comp-bar", inputs


def _case_source_hash_missing():
    inputs = _valid_inputs()
    del inputs["source_hash"]
    return "comp-foo", inputs


CASES = {
    "source_path-escape": _case_source_path_escape,
    "source_path-gen": _case_source_path_gen,
    "source_path-absolute": _case_source_path_abs,
    "owners-empty": _case_owners_empty,
    "owner-Alice": _case_owner_uppercase,
    "source_hash-short": _case_bad_hash,
    "verifier_version-v2": _case_bad_verifier_version,
    "criteria-empty": _case_empty_criteria,
    "component_id-mismatch": _case_component_id_mismatch,
    "source_hash-missing": _case_source_hash_missing,
}


@pytest.mark.parametrize("case_name", sorted(CASES))
def test_invalid_sealed_inputs_raise_and_leave_existing_manifest_untouched(tmp_path, case_name):
    repo_root, manifest, original = _setup_repo(tmp_path)
    before = _snapshot(tmp_path)

    component_id, inputs = CASES[case_name]()

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)

    # The existing manifest's bytes are unchanged.
    assert manifest.read_bytes() == original
    # And nothing else was written anywhere under the test's temp area
    # (covers e.g. "../escape/" and "gen/foo/" targets too).
    assert _snapshot(tmp_path) == before
    assert not (tmp_path / "escape" / ".sealed-provenance.json").exists()
    assert not (repo_root / "gen" / "foo" / ".sealed-provenance.json").exists()


def test_overall_pass_with_failing_criterion_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)
    before = _snapshot(tmp_path)

    inputs = _valid_inputs()
    inputs["verification_report"] = _report(
        criteria=[
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
            },
        ],
        overall="pass",
    )

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").exists()
    assert _snapshot(tmp_path) == before


def test_control_valid_inputs_do_not_raise(tmp_path):
    """Control: the same baseline inputs, unmodified, are accepted, so each
    rejection above is attributable to its single invalid field."""
    repo_root, manifest, _original = _setup_repo(tmp_path)
    inputs = copy.deepcopy(_valid_inputs())

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert manifest.is_file()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    assert doc["component_id"] == "comp-foo"
    assert doc["source_hash"] == VALID_HASH