# hotdocs-criterion: sha256:7a06411704f0767bdfb7417172fe333cb882eaa0d897f7e4cdbaf42e837b06f8
import copy
import json

import pytest

import provenance_writer


VALID_HASH = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _entry(n, result):
    return {
        "id": "AC-FOO-" + str(n).zfill(3),
        "covers": "R-FOO-" + str(n).zfill(3),
        "kind": "compiled",
        "result": result,
    }


def _report(overall, results):
    return {
        "component_id": "comp-foo",
        "criteria": [_entry(i + 1, r) for i, r in enumerate(results)],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def valid_inputs():
    return {
        "component_id": "comp-foo",
        "owners": ["pipeline-team"],
        "source_path": "pipeline/foo/",
        "source_hash": VALID_HASH,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "verification_report": _report("pass", ["pass", "pass"]),
    }


def _snapshot(root):
    snap = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_file():
            snap[rel] = p.read_bytes()
        else:
            snap[rel] = None
    return snap


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "pipeline" / "foo").mkdir(parents=True)
    return repo_root


def _assert_rejected(tmp_path, component_id, inputs):
    repo_root = _setup(tmp_path)
    before = _snapshot(tmp_path)
    with pytest.raises(provenance_writer.InvalidSealedInputError):
        provenance_writer.write_sealed_provenance(component_id, inputs, repo_root)
    after = _snapshot(tmp_path)
    assert after == before, "an invalid call must write nothing"


# --- inputs not a mapping/object at all -------------------------------------

@pytest.mark.parametrize("inputs", [None, [], ["comp-foo"], "comp-foo"],
                         ids=["none", "empty-list", "list", "string"])
def test_non_mapping_inputs_rejected(tmp_path, inputs):
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- each required field missing in turn ------------------------------------

@pytest.mark.parametrize("missing", [
    "component_id", "owners", "source_path", "source_hash",
    "verifier_version", "verification_report",
])
def test_missing_field_rejected(tmp_path, missing):
    inputs = valid_inputs()
    del inputs[missing]
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- one field changed to a bad value ----------------------------------------

UPPER_HEX = ("0123456789ABCDEF" * 4)
assert len(UPPER_HEX) == 64

CHANGED_CASES = [
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
    ("source_hash", "sha256:" + ("0123456789abcdef" * 4)[:63]),
    ("source_hash", "sha256:" + UPPER_HEX),
    ("source_hash", "sha1:" + ("0123456789abcdef" * 4)),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
]


@pytest.mark.parametrize("name,value", CHANGED_CASES,
                         ids=[c[0] + "=" + repr(c[1]) for c in CHANGED_CASES])
def test_changed_field_rejected(tmp_path, name, value):
    inputs = valid_inputs()
    inputs[name] = copy.deepcopy(value)
    component_id = value if name == "component_id" else "comp-foo"
    _assert_rejected(tmp_path, component_id, inputs)


# --- bad verification reports -----------------------------------------------

def _bad_reports():
    no_result = _report("pass", ["pass"])
    del no_result["criteria"][0]["result"]
    criteria_not_list = _report("pass", ["pass"])
    criteria_not_list["criteria"] = {"AC-FOO-001": "pass"}
    return [
        ("none", None),
        ("list", [_entry(1, "pass")]),
        ("overall-ok", _report("ok", ["pass"])),
        ("overall-5", _report(5, ["pass"])),
        ("criteria-not-list", criteria_not_list),
        ("entry-no-result", no_result),
        ("pass-with-skipped", _report("pass", ["pass", "skipped"])),
    ]


BAD_REPORTS = _bad_reports()


@pytest.mark.parametrize("report", [r for _, r in BAD_REPORTS],
                         ids=[i for i, _ in BAD_REPORTS])
def test_bad_report_rejected(tmp_path, report):
    inputs = valid_inputs()
    inputs["verification_report"] = copy.deepcopy(report)
    _assert_rejected(tmp_path, "comp-foo", inputs)


# --- valid fail reports are written ------------------------------------------

def _write_and_read(tmp_path, inputs):
    repo_root = _setup(tmp_path)
    provenance_writer.write_sealed_provenance("comp-foo", inputs, repo_root)
    path = repo_root / "pipeline" / "foo" / ".sealed-provenance.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_fail_report_written(tmp_path):
    inputs = valid_inputs()
    inputs["verification_report"] = _report("fail", ["fail", "fail", "fail"])
    doc = _write_and_read(tmp_path, inputs)
    ch = doc["characterization"]
    assert ch["overall"] == "fail"
    assert ch["criteria_passed"] == 0
    assert ch["criteria_total"] == 3


def test_fail_report_with_skipped_written(tmp_path):
    inputs = valid_inputs()
    inputs["verification_report"] = _report("fail", ["pass", "skipped", "fail", "skipped"])
    doc = _write_and_read(tmp_path, inputs)
    ch = doc["characterization"]
    assert ch["overall"] == "fail"
    assert ch["criteria_passed"] == 1
    assert ch["criteria_total"] == 4


# --- source_path with no trailing slash --------------------------------------

def test_source_path_without_trailing_slash_written_unchanged(tmp_path):
    inputs = valid_inputs()
    inputs["source_path"] = "pipeline/foo"
    doc = _write_and_read(tmp_path, inputs)
    assert doc["source_path"] == "pipeline/foo"
    assert doc["component_id"] == "comp-foo"