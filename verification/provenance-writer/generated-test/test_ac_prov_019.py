import copy
import json
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4
VALID_VERIFIER = "verifier-orchestrator@2.0.0"


def _report(criteria_results=("pass",), overall="pass"):
    criteria = []
    for i, result in enumerate(criteria_results, start=1):
        criteria.append(
            {
                "id": "AC-FOO-%03d" % i,
                "covers": "R-FOO-%03d" % i,
                "kind": "compiled",
                "result": result,
            }
        )
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {
            c["covers"]: ("pass" if c["result"] == "pass" else "fail")
            for c in criteria
        },
        "interface_drift": False,
        "mutation_score": None,
        "overall": overall,
    }


def _base_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": VALID_VERIFIER,
        "verification_report": _report(("pass", "pass")),
    }


def _existing_manifest_bytes():
    doc = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": VALID_VERIFIER,
        "characterization": {
            "overall": "pass",
            "criteria_passed": 2,
            "criteria_total": 2,
        },
        "written_at": "2026-11-02T00:00:00Z",
    }
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _with(key, value):
    def mutate(inputs):
        inputs[key] = value
        return inputs

    return mutate


def _without(key):
    def mutate(inputs):
        del inputs[key]
        return inputs

    return mutate


def _empty_criteria(inputs):
    inputs["verification_report"] = _report(())
    inputs["verification_report"]["criteria"] = []
    inputs["verification_report"]["requirement_results"] = {}
    return inputs


def _identity(inputs):
    return inputs


# (case id, inputs mutation, component_id argument)
CASES = [
    ("source_path_escape", _with("source_path", "../escape/"), "comp-foo"),
    ("source_path_gen", _with("source_path", "gen/foo/"), "comp-foo"),
    ("source_path_absolute", _with("source_path", "/abs/path/"), "comp-foo"),
    ("owners_empty", _with("owners", []), "comp-foo"),
    ("owner_uppercase", _with("owners", ["Alice"]), "comp-foo"),
    ("source_hash_short", _with("source_hash", "sha256:abc"), "comp-foo"),
    ("verifier_version_bad", _with("verifier_version", "v2"), "comp-foo"),
    ("report_criteria_empty", _empty_criteria, "comp-foo"),
    ("component_id_mismatch", _identity, "comp-bar"),
    ("source_hash_missing", _without("source_hash"), "comp-foo"),
]


@pytest.fixture
def repo_with_manifest(tmp_path):
    # Nest the repo one level down so "../escape/" stays inside tmp_path.
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "pipeline" / "foo"
    manifest_dir.mkdir(parents=True)
    manifest = manifest_dir / ".sealed-provenance.json"
    original = _existing_manifest_bytes()
    manifest.write_bytes(original)
    return tmp_path, repo_root, manifest, original


@pytest.mark.parametrize(
    "case_id,mutate,component_arg", CASES, ids=[c[0] for c in CASES]
)
def test_invalid_sealed_inputs_raise_and_leave_manifest_untouched(
    repo_with_manifest, case_id, mutate, component_arg
):
    tmp_root, repo_root, manifest, original = repo_with_manifest
    inputs = mutate(copy.deepcopy(_base_inputs()))

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_arg, inputs, repo_root)

    assert manifest.exists()
    assert manifest.read_bytes() == original

    # Nothing written at the escape target or under gen/.
    assert not (tmp_root / "escape" / ".sealed-provenance.json").exists()
    assert not (repo_root / "gen" / "foo" / ".sealed-provenance.json").exists()


def test_overall_pass_with_failing_entry_raises_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)

    inputs = _base_inputs()
    inputs["verification_report"] = _report(("pass", "fail"), overall="pass")

    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    assert not (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").exists()
    written = [p for p in repo_root.rglob("*") if p.is_file()]
    assert written == []


def test_control_valid_inputs_are_accepted(tmp_path):
    # Guards against the invalid cases passing vacuously: the unmodified
    # base inputs must be valid and produce a manifest.
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)

    provenance_writer.write_sealed_provenance("comp-foo", _base_inputs(), repo_root)

    manifest = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert manifest.exists()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    assert doc["component_id"] == "comp-foo"
    assert doc["characterization"] == {
        "overall": "pass",
        "criteria_passed": 2,
        "criteria_total": 2,
    }