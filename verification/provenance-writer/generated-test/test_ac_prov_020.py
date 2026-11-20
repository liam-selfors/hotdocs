# hotdocs-criterion: sha256:fe8a930caa7fc84d67e6eced2f1aec4485a093fb3dcf1423556a0d83a54d1acd
import copy
import json
from pathlib import Path

import pytest

import provenance_writer


HASH = "sha256:" + "0123456789abcdef" * 4
MANIFEST_NAME = ".sealed-provenance.json"
SENTINEL = b'{"sentinel": "existing manifest, must stay untouched"}\n'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def valid_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
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
        "source_path": "legacy/foo/",
        "source_hash": HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": valid_report(),
    }


def snapshot(root):
    entries = []
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            entries.append((rel, None))
        else:
            entries.append((rel, p.read_bytes()))
    return entries


def prepare_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "legacy" / "foo").mkdir(parents=True)
    (repo_root / "legacy" / "foo" / MANIFEST_NAME).write_bytes(SENTINEL)
    (repo_root / "pipeline" / "foo").mkdir(parents=True)
    return repo_root


def assert_rejected(tmp_path, component_id, inputs):
    repo_root = prepare_repo(tmp_path)
    before = snapshot(repo_root)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    after = snapshot(repo_root)
    assert after == before, "an invalid call wrote something under repo_root"
    assert (repo_root / "legacy" / "foo" / MANIFEST_NAME).read_bytes() == SENTINEL


# --- inputs that are not a mapping/object at all ---------------------------

@pytest.mark.parametrize("bad_inputs", [None, [], ["comp-foo"], "comp-foo"],
                         ids=["none", "empty-list", "list", "string"])
def test_non_mapping_inputs_rejected(tmp_path, bad_inputs):
    assert_rejected(tmp_path, "comp-foo", bad_inputs)


# --- each required field missing in turn ------------------------------------

@pytest.mark.parametrize("missing", [
    "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "verification_report",
])
def test_missing_field_rejected(tmp_path, missing):
    inputs = valid_inputs()
    del inputs[missing]
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- one field changed to an invalid value ----------------------------------

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


@pytest.mark.parametrize("name,value", BAD_FIELD_VALUES,
                         ids=[n + "=" + repr(v) for n, v in BAD_FIELD_VALUES])
def test_invalid_field_value_rejected(tmp_path, name, value):
    inputs = valid_inputs()
    inputs[name] = value
    # For component_id, the argument matches the (invalid) input value.
    component_id = value if name == "component_id" else "comp-foo"
    assert_rejected(tmp_path, component_id, inputs)


# --- invalid verification reports --------------------------------------------

def _report_overall_ok():
    r = valid_report()
    r["overall"] = "ok"
    return r


def _report_overall_int():
    r = valid_report()
    r["overall"] = 5
    return r


def _report_criteria_not_list():
    r = valid_report()
    r["criteria"] = {"AC-FOO-001": "pass"}
    return r


def _report_entry_without_result():
    r = valid_report()
    r["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled"},
    ]
    return r


def _report_pass_with_skipped():
    r = valid_report()
    r["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped",
         "rationale": None},
    ]
    r["overall"] = "pass"
    return r


BAD_REPORTS = [
    ("none", lambda: None),
    ("list", lambda: [valid_report()]),
    ("overall-ok", _report_overall_ok),
    ("overall-5", _report_overall_int),
    ("criteria-not-list", _report_criteria_not_list),
    ("entry-without-result", _report_entry_without_result),
    ("pass-with-skipped", _report_pass_with_skipped),
]


@pytest.mark.parametrize("make_report", [m for _, m in BAD_REPORTS],
                         ids=[i for i, _ in BAD_REPORTS])
def test_invalid_report_rejected(tmp_path, make_report):
    inputs = valid_inputs()
    inputs["verification_report"] = make_report()
    assert_rejected(tmp_path, "comp-foo", inputs)


# --- fail reports are written, counting only pass entries ---------------------

def read_manifest(repo_root, source_path):
    path = Path(repo_root) / source_path / MANIFEST_NAME
    assert path.is_file(), "manifest not written at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_fail_report_written(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "legacy" / "foo").mkdir(parents=True)
    inputs = valid_inputs()
    report = valid_report()
    report["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "fail"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail"},
    ]
    report["overall"] = "fail"
    inputs["verification_report"] = report

    provenance_writer.write_sealed_provenance("comp-foo", copy.deepcopy(inputs), repo_root)

    manifest = read_manifest(repo_root, "legacy/foo/")
    characterization = field(manifest, "characterization")
    assert field(characterization, "overall") == "fail"
    assert field(characterization, "criteria_passed") == 0
    assert field(characterization, "criteria_total") == 2


def test_skipped_entries_report_written(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "legacy" / "foo").mkdir(parents=True)
    inputs = valid_inputs()
    report = valid_report()
    report["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped",
         "rationale": None},
        {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "llm-judge", "result": "skipped",
         "rationale": None},
    ]
    report["overall"] = "fail"
    inputs["verification_report"] = report

    provenance_writer.write_sealed_provenance("comp-foo", copy.deepcopy(inputs), repo_root)

    manifest = read_manifest(repo_root, "legacy/foo/")
    characterization = field(manifest, "characterization")
    assert field(characterization, "overall") == "fail"
    assert field(characterization, "criteria_passed") == 1
    assert field(characterization, "criteria_total") == 3


# --- source_path without trailing slash ---------------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)
    inputs = valid_inputs()
    inputs["source_path"] = "pipeline/foo"

    provenance_writer.write_sealed_provenance("comp-foo", copy.deepcopy(inputs), repo_root)

    manifest_path = repo_root / "pipeline" / "foo" / MANIFEST_NAME
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert field(manifest, "source_path") == "pipeline/foo"
    assert field(manifest, "component_id") == "comp-foo"