# hotdocs-criterion: sha256:28d9d9d1b04f9cff989aba3aed6136bda8cba7c481a22617c940670686933fd4
import copy
import json
from pathlib import Path

import pytest

import provenance_writer


HEX64 = "0123456789abcdef" * 4
SENTINEL = b'{"sentinel": "existing manifest, must stay untouched"}\n'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "source_hash": "sha256:" + HEX64,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": valid_report(),
    }


def snapshot(root):
    entries = []
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            entries.append((rel, "dir", None))
        else:
            entries.append((rel, "file", p.read_bytes()))
    return entries


def prepare_repo(tmp_path):
    repo_root = tmp_path / "repo"
    src = repo_root / "pipeline" / "foo"
    src.mkdir(parents=True)
    (src / "foo.py").write_text("x = 1\n")
    (src / ".sealed-provenance.json").write_bytes(SENTINEL)
    return repo_root


def assert_rejected(tmp_path, component_id, inputs):
    repo_root = prepare_repo(tmp_path)
    before = snapshot(repo_root)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    after = snapshot(repo_root)
    assert after == before, "a rejected call must write nothing"
    assert (repo_root / "pipeline" / "foo" / ".sealed-provenance.json").read_bytes() == SENTINEL


# --- Not a mapping/object at all ---------------------------------------------

@pytest.mark.parametrize("bad", [None, [], ["comp-foo"], "comp-foo"], ids=["none", "empty-list", "list", "string"])
def test_inputs_not_mapping_or_object(tmp_path, bad):
    assert_rejected(tmp_path, "comp-foo", bad)


# --- Each required field missing in turn ---------------------------------------

@pytest.mark.parametrize(
    "missing",
    ["component_id", "owners", "source_path", "source_hash", "verifier_version", "verification_report"],
)
def test_missing_field(tmp_path, missing):
    inputs = valid_inputs()
    del inputs[missing]
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- One field changed to an invalid value ---------------------------------------

@pytest.mark.parametrize("value", [5, "Comp-foo", "foo"], ids=["int", "uppercase", "no-prefix"])
def test_bad_component_id(tmp_path, value):
    inputs = valid_inputs()
    inputs["component_id"] = value
    assert_rejected(tmp_path, value, inputs)


@pytest.mark.parametrize(
    "value",
    ["pipeline-team", [], [5], ["pipeline-team", ""], ["Pipeline"]],
    ids=["string", "empty", "int-entry", "empty-entry", "uppercase-entry"],
)
def test_bad_owners(tmp_path, value):
    inputs = valid_inputs()
    inputs["owners"] = value
    assert_rejected(tmp_path, "comp-foo", inputs)


@pytest.mark.parametrize(
    "value",
    [5, "a b/", "../x/", "gen/foo/", "/abs/"],
    ids=["int", "space", "dotdot", "gen", "absolute"],
)
def test_bad_source_path(tmp_path, value):
    inputs = valid_inputs()
    inputs["source_path"] = value
    assert_rejected(tmp_path, "comp-foo", inputs)


@pytest.mark.parametrize(
    "value",
    [
        5,
        "sha256:" + HEX64[:63],
        "sha256:" + ("0123456789ABCDEF" * 4),
        "sha1:" + HEX64,
    ],
    ids=["int", "63-hex", "uppercase-hex", "sha1-prefix"],
)
def test_bad_source_hash(tmp_path, value):
    inputs = valid_inputs()
    inputs["source_hash"] = value
    assert_rejected(tmp_path, "comp-foo", inputs)


@pytest.mark.parametrize(
    "value",
    [5, "verifier-orchestrator@2", "other@2.0.0"],
    ids=["int", "short-version", "other-name"],
)
def test_bad_verifier_version(tmp_path, value):
    inputs = valid_inputs()
    inputs["verifier_version"] = value
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- Bad verification reports ------------------------------------------------------

def _report_overall_ok():
    r = valid_report()
    r["overall"] = "ok"
    return r


def _report_overall_int():
    r = valid_report()
    r["overall"] = 5
    return r


def _report_criteria_dict():
    r = valid_report()
    r["criteria"] = {"AC-FOO-001": "pass"}
    return r


def _report_criteria_string():
    r = valid_report()
    r["criteria"] = "pass"
    return r


def _report_entry_no_result():
    r = valid_report()
    r["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled"},
    ]
    return r


def _report_pass_with_skipped():
    r = valid_report()
    r["overall"] = "pass"
    r["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": None},
    ]
    return r


@pytest.mark.parametrize(
    "make_report",
    [
        lambda: None,
        lambda: [valid_report()],
        _report_overall_ok,
        _report_overall_int,
        _report_criteria_dict,
        _report_criteria_string,
        _report_entry_no_result,
        _report_pass_with_skipped,
    ],
    ids=[
        "none",
        "list",
        "overall-ok",
        "overall-int",
        "criteria-dict",
        "criteria-string",
        "entry-no-result",
        "pass-with-skipped",
    ],
)
def test_bad_verification_report(tmp_path, make_report):
    inputs = valid_inputs()
    inputs["verification_report"] = make_report()
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- Accepted failing reports -----------------------------------------------------

def _write_and_read(tmp_path, inputs):
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)
    (repo_root / "pipeline" / "foo" / "foo.py").write_text("x = 1\n")
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert path.is_file(), "manifest must be written at <repo_root>/<source_path>/.sealed-provenance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_count(value, expected):
    assert isinstance(value, int) and not isinstance(value, bool)
    assert value == expected


def test_fail_report_all_fail_is_written(tmp_path):
    inputs = valid_inputs()
    report = valid_report()
    report["overall"] = "fail"
    report["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "fail"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail"},
        {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "generated-test", "result": "fail"},
    ]
    inputs["verification_report"] = report
    manifest = _write_and_read(tmp_path, inputs)
    char = field(manifest, "characterization")
    assert field(char, "overall") == "fail"
    _assert_count(field(char, "criteria_passed"), 0)
    _assert_count(field(char, "criteria_total"), 3)


def test_fail_report_with_skipped_is_written(tmp_path):
    inputs = valid_inputs()
    report = valid_report()
    report["overall"] = "fail"
    report["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": None},
        {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "llm-judge", "result": "skipped", "rationale": None},
        {"id": "AC-FOO-004", "covers": "R-FOO-004", "kind": "compiled", "result": "fail"},
    ]
    inputs["verification_report"] = report
    manifest = _write_and_read(tmp_path, inputs)
    char = field(manifest, "characterization")
    assert field(char, "overall") == "fail"
    _assert_count(field(char, "criteria_passed"), 1)
    _assert_count(field(char, "criteria_total"), 4)


# --- source_path without trailing slash ----------------------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    inputs = valid_inputs()
    inputs["source_path"] = "pipeline/foo"
    manifest = _write_and_read(tmp_path, inputs)
    assert field(manifest, "source_path") == "pipeline/foo"
    assert field(manifest, "component_id") == "comp-foo"
    assert field(manifest, "kind") == "sealed-provenance"