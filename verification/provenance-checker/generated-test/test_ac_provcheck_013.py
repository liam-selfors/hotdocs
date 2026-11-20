# hotdocs-criterion: sha256:73b5122e2850493977f6c3d60d93029b01cd991443f51727fbebdb547730d78e
import copy
import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
SOURCE_PATH = "pipeline/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(root, sealed=True):
    root = Path(root)
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team, alice]",
        "depends_on: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: " + SOURCE_PATH)
    lines += [
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
        "A fixture component.",
        "",
    ]
    write(root / "specs" / "components" / "foo" / "component.md", "\n".join(lines))
    write(root / "pipeline" / "foo" / "foo.py", "VALUE = 1\n")
    write(
        root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr(VERIFIER_VERSION) + "\n",
    )
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    adapter = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    write(root / "gen" / "kind-python" / "kind_python.py", adapter)
    return root


def valid_manifest(root):
    key = provenance_checker.current_sealed_key(COMPONENT_ID, root)
    assert key is not None
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": ["pipeline-team", "alice"],
        "source_path": SOURCE_PATH,
        "source_hash": field(key, "source_hash"),
        "verifier_version": VERIFIER_VERSION,
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": "2026-11-02T00:00:00Z",
    }


def write_manifest(root, document):
    write(Path(root) / "pipeline" / "foo" / ".sealed-provenance.json", json.dumps(document))


def assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "sealed") is True
    assert field(result, "hit") is False
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


def test_valid_current_manifest_hits_and_is_sealed(tmp_path):
    root = build_repo(tmp_path)
    write_manifest(root, valid_manifest(root))
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


@pytest.mark.parametrize(
    "document",
    [["kind", "sealed-provenance"], 5, "sealed-provenance", None],
    ids=["list", "number", "string", "null"],
)
def test_non_object_document_is_invalid(tmp_path, document):
    root = build_repo(tmp_path)
    valid_manifest(root)
    write_manifest(root, document)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert_miss(result, "manifest_invalid")


TOP_LEVEL_CHANGES = [
    ("kind", "sealed"),
    ("kind", 5),
    ("version", 2),
    ("version", "1"),
    ("version", 1.0),
    ("component_id", 5),
    ("component_id", "Comp-foo"),
    ("component_id", "foo"),
    ("owners", "pipeline-team"),
    ("owners", []),
    ("owners", [5]),
    ("owners", ["pipeline-team", ""]),
    ("owners", ["Pipeline"]),
    ("source_path", 5),
    ("source_path", "../x/"),
    ("source_path", "gen/foo/"),
    ("source_path", "/abs/"),
    ("source_path", "a b/"),
    ("source_hash", 5),
    ("source_hash", "sha256:" + "a" * 63),
    ("source_hash", "sha256:" + "A" * 64),
    ("source_hash", "sha1:" + "a" * 64),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
    ("written_at", 5),
    ("written_at", "2026-11-02"),
    ("written_at", "2026-11-02 00:00:00Z"),
    ("written_at", "2026-11-02T00:00:00"),
]


@pytest.mark.parametrize(
    "name,value",
    TOP_LEVEL_CHANGES,
    ids=[n + "=" + repr(v) for n, v in TOP_LEVEL_CHANGES],
)
def test_invalid_top_level_field(tmp_path, name, value):
    root = build_repo(tmp_path)
    manifest = valid_manifest(root)
    manifest[name] = copy.deepcopy(value)
    write_manifest(root, manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert_miss(result, "manifest_invalid")


CHARACTERIZATION_CHANGES = [
    ("list", ["pass", 2, 2]),
    ("missing_total", {"overall": "pass", "criteria_passed": 2}),
    ("extra_key", {"overall": "pass", "criteria_passed": 2, "criteria_total": 2, "extra": 1}),
    ("overall_ok", {"overall": "ok", "criteria_passed": 2, "criteria_total": 2}),
    ("overall_5", {"overall": 5, "criteria_passed": 2, "criteria_total": 2}),
    ("passed_string", {"overall": "pass", "criteria_passed": "2", "criteria_total": 2}),
    ("passed_true", {"overall": "pass", "criteria_passed": True, "criteria_total": 2}),
    ("total_negative", {"overall": "pass", "criteria_passed": 2, "criteria_total": -1}),
    ("passed_over_total", {"overall": "pass", "criteria_passed": 3, "criteria_total": 2}),
    ("pass_zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}),
]


@pytest.mark.parametrize(
    "characterization",
    [c for _, c in CHARACTERIZATION_CHANGES],
    ids=[i for i, _ in CHARACTERIZATION_CHANGES],
)
def test_invalid_characterization(tmp_path, characterization):
    root = build_repo(tmp_path)
    manifest = valid_manifest(root)
    manifest["characterization"] = copy.deepcopy(characterization)
    write_manifest(root, manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert_miss(result, "manifest_invalid")


@pytest.mark.parametrize(
    "characterization",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
    ids=["fail_0_of_2", "fail_0_of_0"],
)
def test_failed_characterization_is_valid_but_failed(tmp_path, characterization):
    root = build_repo(tmp_path)
    manifest = valid_manifest(root)
    manifest["characterization"] = copy.deepcopy(characterization)
    write_manifest(root, manifest)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert_miss(result, "characterization_failed")


def test_not_sealed_component(tmp_path):
    root = build_repo(tmp_path, sealed=False)
    assert provenance_checker.current_sealed_key(COMPONENT_ID, root) is None
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, root)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False