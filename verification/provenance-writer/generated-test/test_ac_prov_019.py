import json

import pytest

import provenance_writer


EXISTING_MANIFEST = {
    "kind": "sealed-provenance",
    "version": 1,
    "component_id": "comp-foo",
    "owners": ["pipeline-team"],
    "source_path": "pipeline/foo/",
    "source_hash": "sha256:" + "ab01" * 16,
    "verifier_version": "verifier-orchestrator@1.0.0",
    "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
    "written_at": "2026-01-01T00:00:00Z",
}


def _make_report(results, overall="pass"):
    criteria = [
        {
            "id": "AC-FOO-%03d" % i,
            "covers": "R-FOO-%03d" % i,
            "kind": "compiled",
            "result": result,
        }
        for i, result in enumerate(results, start=1)
    ]
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {c["covers"]: c["result"] for c in criteria},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": overall,
    }


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + "0123456789abcdef" * 4,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": _make_report(["pass", "pass", "pass"]),
    }


def _seed_existing_manifest(repo_root):
    target_dir = repo_root / "pipeline" / "foo"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / ".sealed-provenance.json"
    data = json.dumps(EXISTING_MANIFEST, indent=2).encode("utf-8")
    target.write_bytes(data)
    return target, data


MUTATIONS = [
    ("source_path_escape", lambda i: i.update(source_path="../escape/")),
    ("source_path_gen", lambda i: i.update(source_path="gen/foo/")),
    ("source_path_abs", lambda i: i.update(source_path="/abs/path/")),
    ("owners_empty", lambda i: i.update(owners=[])),
    ("owner_bad_format", lambda i: i.update(owners=["Alice"])),
    ("source_hash_bad", lambda i: i.update(source_hash="sha256:abc")),
    ("verifier_version_bad", lambda i: i.update(verifier_version="v2")),
    ("criteria_empty", lambda i: i.update(verification_report=_make_report([]))),
    ("source_hash_missing", lambda i: i.pop("source_hash")),
]


@pytest.mark.parametrize("name, mutate", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_invalid_input_rejected_and_existing_manifest_unchanged(tmp_path, name, mutate):
    repo_root = tmp_path
    manifest_path, original_bytes = _seed_existing_manifest(repo_root)

    inputs = _valid_inputs()
    mutate(inputs)

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert manifest_path.read_bytes() == original_bytes


def test_component_id_mismatch_rejected_and_existing_manifest_unchanged(tmp_path):
    repo_root = tmp_path
    manifest_path, original_bytes = _seed_existing_manifest(repo_root)

    inputs = _valid_inputs()

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-bar", inputs, repo_root)

    assert manifest_path.read_bytes() == original_bytes


def test_overall_pass_with_failing_criterion_rejected_and_no_file_written(tmp_path):
    repo_root = tmp_path
    target = repo_root / "pipeline" / "bar" / ".sealed-provenance.json"
    assert not target.exists()

    inputs = _valid_inputs()
    inputs["component_id"] = "comp-bar"
    inputs["source_path"] = "pipeline/bar/"
    inputs["verification_report"] = _make_report(["pass", "fail"], overall="pass")

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-bar", inputs, repo_root)

    assert not target.exists()