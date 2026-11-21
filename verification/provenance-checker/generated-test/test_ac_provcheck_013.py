# hotdocs-criterion: sha256:64ba495bb8152358e3edf7b698faa9168fb6fcae08d169703ac5147c7a06df46
import copy
import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_python_adapter(repo_root):
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    guidance_result = {"generator": "", "test_author": ""}
    src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance_result) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _plant_verifier(repo_root):
    src = "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", src)


def _plant_component(repo_root, sealed=True):
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
    _write(repo_root / "pipeline" / "foo" / "foo.py", "X = 1\n")


def _build_repo(repo_root, sealed=True):
    _plant_python_adapter(repo_root)
    _plant_verifier(repo_root)
    _plant_component(repo_root, sealed=sealed)


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


def _current_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    return field(key, "source_hash")


def _check(repo_root):
    return provenance_checker.check_sealed_provenance("comp-foo", repo_root)


def _assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None


# --- valid, current manifest is a hit (baseline) ---------------------------

def test_valid_current_manifest_hits(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    manifest = _valid_manifest(_current_hash(repo_root))
    _write(_manifest_path(repo_root), json.dumps(manifest))
    result = _check(repo_root)
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


# --- the document is not an object -----------------------------------------

@pytest.mark.parametrize(
    "make_doc",
    [
        lambda m: [m],
        lambda m: 5,
        lambda m: "sealed-provenance",
        lambda m: None,
    ],
    ids=["list", "number", "string", "null"],
)
def test_non_object_document_is_invalid(tmp_path, make_doc):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    manifest = _valid_manifest(_current_hash(repo_root))
    _write(_manifest_path(repo_root), json.dumps(make_doc(manifest)))
    _assert_miss(_check(repo_root), "manifest_invalid")


# --- one top-level field changed --------------------------------------------

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
    "key,value",
    TOP_LEVEL_CHANGES,
    ids=[k + "=" + repr(v) for k, v in TOP_LEVEL_CHANGES],
)
def test_invalid_top_level_field(tmp_path, key, value):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    manifest = _valid_manifest(_current_hash(repo_root))
    manifest[key] = copy.deepcopy(value)
    _write(_manifest_path(repo_root), json.dumps(manifest))
    _assert_miss(_check(repo_root), "manifest_invalid")


# --- characterization changed -----------------------------------------------

def _without_total():
    return {"overall": "pass", "criteria_passed": 2}


CHARACTERIZATION_CHANGES = [
    ("list", ["pass", 2, 2]),
    ("missing_total", _without_total()),
    ("extra_key", {"overall": "pass", "criteria_passed": 2, "criteria_total": 2, "extra": 1}),
    ("overall_ok", {"overall": "ok", "criteria_passed": 2, "criteria_total": 2}),
    ("overall_5", {"overall": 5, "criteria_passed": 2, "criteria_total": 2}),
    ("passed_str", {"overall": "pass", "criteria_passed": "2", "criteria_total": 2}),
    ("passed_true", {"overall": "pass", "criteria_passed": True, "criteria_total": 2}),
    ("total_negative", {"overall": "pass", "criteria_passed": 2, "criteria_total": -1}),
    ("passed_gt_total", {"overall": "pass", "criteria_passed": 3, "criteria_total": 2}),
    ("pass_zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}),
]


@pytest.mark.parametrize(
    "value",
    [v for _, v in CHARACTERIZATION_CHANGES],
    ids=[n for n, _ in CHARACTERIZATION_CHANGES],
)
def test_invalid_characterization(tmp_path, value):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    manifest = _valid_manifest(_current_hash(repo_root))
    manifest["characterization"] = copy.deepcopy(value)
    _write(_manifest_path(repo_root), json.dumps(manifest))
    _assert_miss(_check(repo_root), "manifest_invalid")


# --- valid failing characterization -----------------------------------------

@pytest.mark.parametrize(
    "value",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
    ids=["fail_0_of_2", "fail_0_of_0"],
)
def test_failed_characterization_is_valid(tmp_path, value):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    manifest = _valid_manifest(_current_hash(repo_root))
    manifest["characterization"] = copy.deepcopy(value)
    _write(_manifest_path(repo_root), json.dumps(manifest))
    _assert_miss(_check(repo_root), "characterization_failed")


# --- not sealed ---------------------------------------------------------------

def test_not_sealed_component(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root, sealed=False)
    assert provenance_checker.current_sealed_key("comp-foo", repo_root) is None
    result = _check(repo_root)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None