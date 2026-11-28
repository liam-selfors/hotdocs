# hotdocs-criterion: sha256:219f3801e82a279986095f2067956c4f755b7915a0d2b925d7b4c14efc44da09
import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, sealed=True):
    # Fake python adapter (testing.md, "The fake python adapter").
    _write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr({
            "ok": True,
            "reason": "",
            "versions": {"python": "3.12.4", "packages": PK},
            "lockfile_sha256": None,
            "interpreter": "/fake/python",
        }) + "\n",
    )

    # verifier-orchestrator stand-in, providing every name its interface lists.
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    return " + repr({
            "component_id": "comp-foo",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": None,
            "mutation_error": None,
            "assets": [],
            "drivers": [],
            "overall": "pass",
        }) + "\n",
    )

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
        lines.append("source_path: pipeline/foo/")
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A fixture component.")
    lines.append("")
    _write(repo_root / "specs" / "components" / "foo" / "component.md", "\n".join(lines))

    # Sealed source.
    _write(repo_root / "pipeline" / "foo" / "foo.py", "def foo():\n    return 1\n")


def _source_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    return field(key, "source_hash")


def _valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": ["pipeline-team", "alice"],
        "source_path": "pipeline/foo/",
        "source_hash": source_hash,
        "verifier_version": "verifier-orchestrator@2.0.0",
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": "2026-11-02T00:00:00Z",
    }


def _manifest_path(repo_root):
    return repo_root / "pipeline" / "foo" / ".sealed-provenance.json"


def _write_manifest_doc(repo_root, doc):
    _manifest_path(repo_root).write_text(json.dumps(doc), encoding="utf-8")


def _check(repo_root):
    return provenance_checker.check_sealed_provenance("comp-foo", repo_root)


def _assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "sealed") is True
    assert field(result, "hit") is False
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, sealed=True)
    source_hash = _source_hash(repo_root)
    return repo_root, source_hash


def test_valid_current_manifest_hits(repo):
    repo_root, source_hash = repo
    _write_manifest_doc(repo_root, _valid_manifest(source_hash))
    result = _check(repo_root)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


@pytest.mark.parametrize("doc", [[], [1, 2], 5, "sealed-provenance", None])
def test_non_object_document_is_invalid(repo, doc):
    repo_root, _ = repo
    _write_manifest_doc(repo_root, doc)
    _assert_miss(_check(repo_root), "manifest_invalid")


TOP_LEVEL_CASES = [
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
    ("source_hash", "sha256:" + "0" * 63),
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


@pytest.mark.parametrize("key,value", TOP_LEVEL_CASES, ids=[k + "=" + repr(v) for k, v in TOP_LEVEL_CASES])
def test_invalid_top_level_field(repo, key, value):
    repo_root, source_hash = repo
    doc = _valid_manifest(source_hash)
    doc[key] = value
    _write_manifest_doc(repo_root, doc)
    _assert_miss(_check(repo_root), "manifest_invalid")


CHARACTERIZATION_CASES = [
    ("list", [{"overall": "pass", "criteria_passed": 2, "criteria_total": 2}]),
    ("missing_total", {"overall": "pass", "criteria_passed": 2}),
    ("extra_key", {"overall": "pass", "criteria_passed": 2, "criteria_total": 2, "extra": 1}),
    ("overall_ok", {"overall": "ok", "criteria_passed": 2, "criteria_total": 2}),
    ("overall_5", {"overall": 5, "criteria_passed": 2, "criteria_total": 2}),
    ("passed_str", {"overall": "pass", "criteria_passed": "2", "criteria_total": 2}),
    ("passed_bool", {"overall": "pass", "criteria_passed": True, "criteria_total": 2}),
    ("total_negative", {"overall": "pass", "criteria_passed": 2, "criteria_total": -1}),
    ("passed_gt_total", {"overall": "pass", "criteria_passed": 3, "criteria_total": 2}),
    ("pass_zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}),
]


@pytest.mark.parametrize("label,value", CHARACTERIZATION_CASES, ids=[c[0] for c in CHARACTERIZATION_CASES])
def test_invalid_characterization(repo, label, value):
    repo_root, source_hash = repo
    doc = _valid_manifest(source_hash)
    doc["characterization"] = copy.deepcopy(value)
    _write_manifest_doc(repo_root, doc)
    _assert_miss(_check(repo_root), "manifest_invalid")


@pytest.mark.parametrize(
    "value",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
    ids=["fail_0_of_2", "fail_0_of_0"],
)
def test_failed_characterization_is_valid_manifest(repo, value):
    repo_root, source_hash = repo
    doc = _valid_manifest(source_hash)
    doc["characterization"] = copy.deepcopy(value)
    _write_manifest_doc(repo_root, doc)
    _assert_miss(_check(repo_root), "characterization_failed")


def test_not_sealed_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, sealed=False)
    # A manifest present at the would-be source path changes nothing.
    _write_manifest_doc(repo_root, _valid_manifest("sha256:" + "0" * 64))
    result = _check(repo_root)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False