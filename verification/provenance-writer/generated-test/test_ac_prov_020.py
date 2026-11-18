# hotdocs-criterion: sha256:c6aed2f1ecafc7176716659768d2e8c18563619e61e59a188d901fb520c9ddcc
import copy
import json
from pathlib import Path

import pytest

import provenance_writer


HEX64 = "0123456789abcdef" * 4

EXISTING_MANIFEST = b'{"sentinel": "existing manifest, must stay untouched"}\n'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "overall": "pass",
    }


def valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": "sha256:" + HEX64,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": valid_report(),
    }


def with_change(name, value):
    inputs = valid_inputs()
    inputs[name] = value
    return inputs


def report_with(**changes):
    report = valid_report()
    report.update(changes)
    return report


def report_entry_without_result():
    report = valid_report()
    del report["criteria"][1]["result"]
    return report


def report_pass_with_skipped():
    report = valid_report()
    report["criteria"][1]["result"] = "skipped"
    report["overall"] = "pass"
    return report


def make_repo(tmp_path):
    outer = tmp_path / "outer"
    repo_root = outer / "repo"
    target = repo_root / "pipeline" / "foo"
    target.mkdir(parents=True)
    (target / ".sealed-provenance.json").write_bytes(EXISTING_MANIFEST)
    (target / "foo.py").write_text("x = 1\n")
    return outer, repo_root


def snapshot(root):
    result = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            result[rel] = None
        else:
            result[rel] = p.read_bytes()
    return result


def assert_rejected(tmp_path, component_id, inputs):
    outer, repo_root = make_repo(tmp_path)
    before = snapshot(outer)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, copy.deepcopy(inputs), repo_root)
    after = snapshot(outer)
    assert after == before, "a rejected call must write nothing"
    assert (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").read_bytes() == EXISTING_MANIFEST


# --- inputs not a mapping/object at all ---------------------------------

@pytest.mark.parametrize("inputs", [None, [], ["comp-foo"], "comp-foo"], ids=["none", "empty-list", "list", "string"])
def test_inputs_not_mapping_rejected(tmp_path, inputs):
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- each field missing in turn -----------------------------------------

@pytest.mark.parametrize(
    "missing",
    ["component_id", "owners", "source_path", "source_hash", "verifier_version", "verification_report"],
)
def test_missing_field_rejected(tmp_path, missing):
    inputs = valid_inputs()
    del inputs[missing]
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- component_id mismatch with argument --------------------------------

def test_component_id_mismatch_rejected(tmp_path):
    assert_rejected(tmp_path, "comp-bar", valid_inputs())


# --- bad component_id (argument matching it) ----------------------------

@pytest.mark.parametrize("bad", [5, "Comp-foo", "foo"], ids=["int", "uppercase", "no-prefix"])
def test_bad_component_id_rejected(tmp_path, bad):
    assert_rejected(tmp_path, bad, with_change("component_id", bad))


# --- one field changed ---------------------------------------------------

BAD_FIELDS = [
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
    ("source_hash", "sha256:" + HEX64[:63]),
    ("source_hash", "sha256:" + HEX64.upper()),
    ("source_hash", "sha1:" + HEX64),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
]


@pytest.mark.parametrize(
    "name,value",
    BAD_FIELDS,
    ids=[n + "-" + repr(v)[:40] for n, v in BAD_FIELDS],
)
def test_bad_field_rejected(tmp_path, name, value):
    assert_rejected(tmp_path, "comp-foo", with_change(name, value))


# --- bad verification reports -------------------------------------------

BAD_REPORTS = [
    ("none", None),
    ("list", [valid_report()]),
    ("overall-ok", report_with(overall="ok")),
    ("overall-int", report_with(overall=5)),
    ("criteria-string", report_with(criteria="AC-FOO-001")),
    ("criteria-dict", report_with(criteria={"AC-FOO-001": "pass"})),
    ("entry-no-result", report_entry_without_result()),
    ("pass-with-skipped", report_pass_with_skipped()),
]


@pytest.mark.parametrize("report", [r for _, r in BAD_REPORTS], ids=[i for i, _ in BAD_REPORTS])
def test_bad_report_rejected(tmp_path, report):
    assert_rejected(tmp_path, "comp-foo", with_change("verification_report", report))


# --- valid "fail" reports are written -----------------------------------

def read_manifest(path):
    assert path.is_file(), "expected manifest at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_fail_report_written(tmp_path):
    _, repo_root = make_repo(tmp_path)
    report = valid_report()
    for c in report["criteria"]:
        c["result"] = "fail"
    report["overall"] = "fail"
    report["requirement_results"] = {"R-FOO-001": "fail", "R-FOO-002": "fail"}
    inputs = with_change("verification_report", report)

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    assert manifest["characterization"] == {"overall": "fail", "criteria_passed": 0, "criteria_total": 2}
    assert manifest["component_id"] == "comp-foo"


def test_skipped_entries_report_written(tmp_path):
    _, repo_root = make_repo(tmp_path)
    report = valid_report()
    report["criteria"].append(
        {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "llm-judge", "result": "skipped", "rationale": None}
    )
    report["criteria"].append(
        {"id": "AC-FOO-004", "covers": "R-FOO-004", "kind": "llm-judge", "result": "skipped", "rationale": None}
    )
    report["overall"] = "fail"
    inputs = with_change("verification_report", report)

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    assert manifest["characterization"] == {"overall": "fail", "criteria_passed": 2, "criteria_total": 4}


# --- source_path without trailing slash ---------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    _, repo_root = make_repo(tmp_path)
    inputs = with_change("source_path", "pipeline/foo")

    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)

    manifest = read_manifest(repo_root / "pipeline" / "foo" / ".sealed-provenance.json")
    assert manifest["source_path"] == "pipeline/foo"
    assert manifest["characterization"] == {"overall": "pass", "criteria_passed": 2, "criteria_total": 2}