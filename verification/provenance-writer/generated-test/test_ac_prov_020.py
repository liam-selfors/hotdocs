import provenance_writer

import copy
import json
import os
from pathlib import Path

import pytest


VALID_HASH = "sha256:" + "0123456789abcdef" * 4


def _report(overall="pass", results=("pass", "pass", "pass")):
    criteria = []
    for i, r in enumerate(results, start=1):
        criteria.append(
            {
                "id": "AC-FOO-%03d" % i,
                "covers": "R-FOO-%03d" % i,
                "kind": "compiled",
                "result": r,
            }
        )
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
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": _report(),
    }


def _files_under(root):
    found = []
    for dirpath, _dirnames, filenames in os.walk(str(root)):
        for name in filenames:
            found.append(os.path.join(dirpath, name))
    return found


def _repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def _assert_rejected(tmp_path, component_id, inputs):
    repo_root = _repo(tmp_path)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    assert _files_under(tmp_path) == [], "an invalid input must write nothing"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# --- Inputs that are not a mapping/object at all -------------------------

@pytest.mark.parametrize(
    "bad_inputs",
    [None, [], ["comp-foo"], "comp-foo"],
    ids=["none", "empty-list", "list", "string"],
)
def test_non_mapping_inputs_rejected(tmp_path, bad_inputs):
    _assert_rejected(tmp_path, "comp-foo", bad_inputs)


# --- Each required field missing in turn ----------------------------------

@pytest.mark.parametrize(
    "missing",
    [
        "component_id",
        "owners",
        "source_path",
        "source_hash",
        "verifier_version",
        "verification_report",
    ],
)
def test_missing_field_rejected(tmp_path, missing):
    inputs = _valid_inputs()
    del inputs[missing]
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- component_id invalid (argument matching it) --------------------------

@pytest.mark.parametrize("bad", [5, "Comp-foo", "foo"], ids=["int", "uppercase", "no-prefix"])
def test_bad_component_id_rejected(tmp_path, bad):
    inputs = _valid_inputs()
    inputs["component_id"] = bad
    _assert_rejected(tmp_path, bad, inputs)


# --- One field changed to an invalid value --------------------------------

BAD_FIELD_CASES = [
    ("owners", "pipeline-team", "owners-string"),
    ("owners", [], "owners-empty"),
    ("owners", [5], "owners-int-entry"),
    ("owners", ["pipeline-team", ""], "owners-empty-entry"),
    ("owners", ["Pipeline"], "owners-uppercase"),
    ("source_path", 5, "source_path-int"),
    ("source_path", "a b/", "source_path-space"),
    ("source_path", "../x/", "source_path-dotdot"),
    ("source_path", "gen/foo/", "source_path-gen"),
    ("source_path", "/abs/", "source_path-absolute"),
    ("source_hash", 5, "source_hash-int"),
    ("source_hash", "sha256:" + "a" * 63, "source_hash-63-hex"),
    ("source_hash", "sha256:" + "A" * 64, "source_hash-uppercase"),
    ("source_hash", "sha1:" + "a" * 64, "source_hash-sha1"),
    ("verifier_version", 5, "verifier_version-int"),
    ("verifier_version", "verifier-orchestrator@2", "verifier_version-short"),
    ("verifier_version", "other@2.0.0", "verifier_version-other"),
]


@pytest.mark.parametrize(
    "name,value",
    [(n, v) for n, v, _ in BAD_FIELD_CASES],
    ids=[i for _, _, i in BAD_FIELD_CASES],
)
def test_bad_field_value_rejected(tmp_path, name, value):
    inputs = _valid_inputs()
    inputs[name] = copy.deepcopy(value)
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- Invalid verification reports -----------------------------------------

def _bad_reports():
    cases = []
    cases.append((None, "none"))
    cases.append(([_report()], "list"))

    r = _report()
    r["overall"] = "ok"
    cases.append((r, "overall-ok"))

    r = _report()
    r["overall"] = 5
    cases.append((r, "overall-int"))

    r = _report()
    r["criteria"] = {"AC-FOO-001": "pass"}
    cases.append((r, "criteria-not-list"))

    r = _report()
    del r["criteria"][1]["result"]
    cases.append((r, "entry-without-result"))

    r = _report(overall="pass", results=("pass", "skipped", "pass"))
    cases.append((r, "pass-with-skipped"))
    return cases


@pytest.mark.parametrize(
    "report",
    [c for c, _ in _bad_reports()],
    ids=[i for _, i in _bad_reports()],
)
def test_bad_verification_report_rejected(tmp_path, report):
    inputs = _valid_inputs()
    inputs["verification_report"] = report
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- Valid "fail" reports are written --------------------------------------

def _read_manifest(path):
    assert path.is_file(), "expected manifest at %s" % path
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_fail_report_all_fail_written(tmp_path):
    repo_root = _repo(tmp_path)
    inputs = _valid_inputs()
    inputs["verification_report"] = _report(overall="fail", results=("fail", "fail", "fail"))

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    assert manifest["kind"] == "sealed-provenance"
    assert manifest["component_id"] == "comp-foo"
    char = field(manifest, "characterization")
    assert char["overall"] == "fail"
    assert char["criteria_passed"] == 0
    assert char["criteria_total"] == 3


def test_fail_report_with_skipped_entries_written(tmp_path):
    repo_root = _repo(tmp_path)
    inputs = _valid_inputs()
    inputs["verification_report"] = _report(
        overall="fail", results=("pass", "skipped", "fail", "skipped")
    )

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    char = manifest["characterization"]
    assert char["overall"] == "fail"
    assert char["criteria_passed"] == 1
    assert char["criteria_total"] == 4


# --- source_path without trailing slash -----------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    repo_root = _repo(tmp_path)
    inputs = _valid_inputs()
    inputs["source_path"] = "pipeline/foo"

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = _read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    assert manifest["source_path"] == "pipeline/foo"
    assert manifest["component_id"] == "comp-foo"
    assert manifest["characterization"]["overall"] == "pass"