import copy
import json
from pathlib import Path

import pytest

import provenance_writer


VALID_HASH = "sha256:" + "0123456789abcdef" * 4
EXISTING_CONTENT = b'{"existing": true}\n'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _report(overall="pass", results=("pass",)):
    criteria = []
    req = {}
    for i, r in enumerate(results, start=1):
        cid = "AC-FOO-%03d" % i
        rid = "R-FOO-%03d" % i
        criteria.append({"id": cid, "covers": rid, "kind": "compiled", "result": r})
        req[rid] = "pass" if r == "pass" else "fail"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": req,
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


def _prepare_repo(repo_root: Path):
    d = repo_root / "pipeline" / "foo"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".sealed-provenance.json").write_bytes(EXISTING_CONTENT)


def _snapshot(repo_root: Path):
    return {
        str(p.relative_to(repo_root)): p.read_bytes()
        for p in sorted(repo_root.rglob("*"))
        if p.is_file()
    }


def _assert_rejected(component_id, inputs, repo_root: Path):
    _prepare_repo(repo_root)
    before = _snapshot(repo_root)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    after = _snapshot(repo_root)
    assert after == before
    assert (
        repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    ).read_bytes() == EXISTING_CONTENT


# --- Not a mapping/object at all -------------------------------------------

@pytest.mark.parametrize("bad", [None, [], ["comp-foo"], "comp-foo"],
                         ids=["none", "empty-list", "list", "string"])
def test_non_mapping_inputs_rejected(tmp_path, bad):
    _assert_rejected("comp-foo", bad, tmp_path)


# --- Each field missing in turn --------------------------------------------

@pytest.mark.parametrize("missing", [
    "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "verification_report",
])
def test_missing_field_rejected(tmp_path, missing):
    inputs = _valid_inputs()
    del inputs[missing]
    _assert_rejected("comp-foo", inputs, tmp_path)


# --- One field changed to a bad value ---------------------------------------

BAD_FIELD_VALUES = [
    ("component_id", 5),
    ("component_id", "Comp-foo"),
    ("component_id", "foo"),
    ("owners", "pipeline-team"),
    ("owners", []),
    ("owners", [5]),
    ("owners", ["pipeline-team", ""]),
    ("owners", ["Pipeline"]),
    ("source_path", 5),
    ("source_path", "a b/"),
    ("source_path", "../x/"),
    ("source_path", "gen/foo/"),
    ("source_path", "/abs/"),
    ("source_hash", 5),
    ("source_hash", "sha256:" + "a" * 63),
    ("source_hash", "sha256:" + "ABCDEF0123456789" * 4),
    ("source_hash", "sha1:" + "a" * 64),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
]


@pytest.mark.parametrize(
    "name,value", BAD_FIELD_VALUES,
    ids=["%s-%d" % (n, i) for i, (n, _v) in enumerate(BAD_FIELD_VALUES)],
)
def test_bad_field_value_rejected(tmp_path, name, value):
    inputs = _valid_inputs()
    inputs[name] = value
    component_id = value if name == "component_id" else "comp-foo"
    _assert_rejected(component_id, inputs, tmp_path)


# --- Bad verification reports ----------------------------------------------

def _bad_reports():
    r_ok = _report()
    r_ok["overall"] = "ok"
    r_five = _report()
    r_five["overall"] = 5
    r_criteria_not_list = _report()
    r_criteria_not_list["criteria"] = "AC-FOO-001"
    r_no_result = _report(results=("pass", "pass"))
    del r_no_result["criteria"][1]["result"]
    r_pass_with_skipped = _report(overall="pass", results=("pass", "skipped"))
    return [
        ("none", None),
        ("list", [copy.deepcopy(_report())]),
        ("overall-ok", r_ok),
        ("overall-5", r_five),
        ("criteria-not-list", r_criteria_not_list),
        ("entry-without-result", r_no_result),
        ("pass-with-skipped", r_pass_with_skipped),
    ]


@pytest.mark.parametrize("report", [r for _i, r in _bad_reports()],
                         ids=[i for i, _r in _bad_reports()])
def test_bad_verification_report_rejected(tmp_path, report):
    inputs = _valid_inputs()
    inputs["verification_report"] = report
    _assert_rejected("comp-foo", inputs, tmp_path)


# --- Valid "fail" reports are written ---------------------------------------

def _read_manifest(repo_root: Path, rel_dir: str):
    path = repo_root / rel_dir / ".sealed-provenance.json"
    assert path.is_file(), "manifest not written at %s" % path
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "results,expected_passed",
    [
        (("fail", "fail", "fail"), 0),
        (("pass", "skipped", "skipped", "fail"), 1),
    ],
    ids=["all-fail", "with-skipped"],
)
def test_fail_report_is_written(tmp_path, results, expected_passed):
    (tmp_path / "pipeline" / "foo").mkdir(parents=True)
    inputs = _valid_inputs()
    inputs["verification_report"] = _report(overall="fail", results=results)
    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)
    manifest = _read_manifest(tmp_path, "pipeline/foo")
    characterization = manifest["characterization"]
    assert characterization["overall"] == "fail"
    assert characterization["criteria_passed"] == expected_passed
    assert type(characterization["criteria_passed"]) is int
    assert characterization["criteria_total"] == len(results)


# --- No trailing slash is written unchanged ---------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    (tmp_path / "pipeline" / "foo").mkdir(parents=True)
    inputs = _valid_inputs()
    inputs["source_path"] = "pipeline/foo"
    provenance_writer.write_sealed_provenance("comp-foo", inputs, tmp_path)
    manifest = _read_manifest(tmp_path, "pipeline/foo")
    assert manifest["source_path"] == "pipeline/foo"