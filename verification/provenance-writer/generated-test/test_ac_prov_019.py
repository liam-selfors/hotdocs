# hotdocs-criterion: sha256:8a9eaaef57e1f5fe95c5c1c9d4aa7926b30f534af9549a337a2229466ae390b1
"""AC-PROV-019: write_sealed_provenance validates before writing, never invents.

Covers R-PROV-019.
"""
import copy
import json
import os
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4
VALID_VERIFIER = "verifier-orchestrator@2.0.0"
SOURCE_PATH = "pipeline/foo/"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _report(criteria_results, overall):
    criteria = []
    requirement_results = {}
    for i, result in enumerate(criteria_results, start=1):
        cid = "AC-FOO-" + str(i).zfill(3)
        rid = "R-FOO-" + str(i).zfill(3)
        criteria.append(
            {"id": cid, "covers": rid, "kind": "compiled", "result": result}
        )
        requirement_results[rid] = "pass" if result == "pass" else "fail"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": overall,
    }


def _valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": SOURCE_PATH,
        "source_hash": VALID_HASH,
        "verifier_version": VALID_VERIFIER,
        "verification_report": _report(["pass", "pass", "pass"], "pass"),
    }


def _existing_manifest_bytes():
    manifest = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": SOURCE_PATH,
        "source_hash": VALID_HASH,
        "verifier_version": VALID_VERIFIER,
        "characterization": {
            "overall": "pass",
            "criteria_passed": 3,
            "criteria_total": 3,
        },
        "written_at": "2026-11-02T00:00:00Z",
    }
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _snapshot(root):
    """Map every file under root (hidden files included) to its bytes."""
    result = {}
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            p = Path(dirpath) / name
            result[str(p.relative_to(root))] = p.read_bytes()
    return result


def _variant_inputs(variant):
    inputs = _valid_inputs()
    component_arg = "comp-foo"
    if variant == "source_path_escape":
        inputs["source_path"] = "../escape/"
    elif variant == "source_path_gen":
        inputs["source_path"] = "gen/foo/"
    elif variant == "source_path_absolute":
        inputs["source_path"] = "/abs/path/"
    elif variant == "owners_empty":
        inputs["owners"] = []
    elif variant == "owner_uppercase":
        inputs["owners"] = ["Alice"]
    elif variant == "source_hash_short":
        inputs["source_hash"] = "sha256:abc"
    elif variant == "verifier_version_bad":
        inputs["verifier_version"] = "v2"
    elif variant == "criteria_empty":
        report = copy.deepcopy(inputs["verification_report"])
        report["criteria"] = []
        report["requirement_results"] = {}
        inputs["verification_report"] = report
    elif variant == "component_id_mismatch":
        component_arg = "comp-bar"
    elif variant == "source_hash_missing":
        del inputs["source_hash"]
    else:  # pragma: no cover
        raise AssertionError("unknown variant " + repr(variant))
    return component_arg, inputs


VARIANTS = [
    "source_path_escape",
    "source_path_gen",
    "source_path_absolute",
    "owners_empty",
    "owner_uppercase",
    "source_hash_short",
    "verifier_version_bad",
    "criteria_empty",
    "component_id_mismatch",
    "source_hash_missing",
]


@pytest.mark.parametrize("variant", VARIANTS)
def test_invalid_input_raises_and_existing_manifest_untouched(tmp_path, variant):
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / ".sealed-provenance.json"
    original = _existing_manifest_bytes()
    manifest_path.write_bytes(original)

    before = _snapshot(repo_root)

    component_arg, inputs = _variant_inputs(variant)

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_arg, inputs, repo_root)

    assert manifest_path.is_file()
    assert manifest_path.read_bytes() == original
    # Nothing else was written anywhere under repo_root either.
    assert _snapshot(repo_root) == before
    # The escaping path must not have produced a manifest outside repo_root.
    assert not (tmp_path / "escape" / ".sealed-provenance.json").exists()
    assert not (repo_root / "gen" / "foo" / ".sealed-provenance.json").exists()


def test_overall_pass_with_failing_entry_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest_path = manifest_dir / ".sealed-provenance.json"

    inputs = _valid_inputs()
    inputs["verification_report"] = _report(["pass", "fail", "pass"], "pass")

    before = _snapshot(repo_root)
    assert before == {}

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not manifest_path.exists()
    assert _snapshot(repo_root) == {}