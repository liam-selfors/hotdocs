"""AC-PROVCHECK-013 — check_sealed_provenance manifest validity (R-PROVCHECK-008)."""
import json

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SEALED_SLUG = "sealed-foo"
SEALED_ID = "comp-sealed-foo"
SOURCE_PATH = "pipeline/sealed-foo/"

UNSEALED_SLUG = "plain-foo"
UNSEALED_ID = "comp-plain-foo"


def _write_verifier_orchestrator(root):
    mod_dir = root / "gen" / "verifier-orchestrator"
    mod_dir.mkdir(parents=True)
    (mod_dir / "verifier_orchestrator.py").write_text(
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
    )


def _write_sealed_component(root):
    comp_dir = root / "specs" / "components" / SEALED_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: {SEALED_ID}\n"
        "title: Sealed Foo\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        f"source_path: {SOURCE_PATH}\n"
        "depends_on: []\n"
        'last_ratified_commit: "0000000"\n'
        "---\n\n"
        "# Sealed Foo\n\n"
        "Purpose: test fixture for sealed provenance checking.\n"
    )
    src_dir = root / SOURCE_PATH
    src_dir.mkdir(parents=True)
    (src_dir / "foo.py").write_text("def foo():\n    return 1\n")


def _write_unsealed_component(root):
    comp_dir = root / "specs" / "components" / UNSEALED_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: {UNSEALED_ID}\n"
        "title: Plain Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n\n"
        "# Plain Foo\n\n"
        "Purpose: not a sealed component.\n"
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write_verifier_orchestrator(root)
    _write_sealed_component(root)
    return root


@pytest.fixture
def valid_manifest(repo_root):
    key = provenance_checker.current_sealed_key(SEALED_ID, repo_root)
    assert key is not None
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": SEALED_ID,
        "owners": list(_get(key, "owners")),
        "source_path": _get(key, "source_path"),
        "source_hash": _get(key, "source_hash"),
        "verifier_version": _get(key, "verifier_version"),
        "characterization": {
            "overall": "pass",
            "criteria_passed": 3,
            "criteria_total": 3,
        },
        "written_at": "2026-11-02T00:00:00Z",
    }


def _write_manifest_text(root, text):
    path = root / SOURCE_PATH / ".sealed-provenance.json"
    path.write_text(text)


def _write_manifest(root, manifest_obj):
    _write_manifest_text(root, json.dumps(manifest_obj))


def _assert_miss(result, reason):
    assert _get(result, "reason") == reason
    assert _get(result, "hit") is False
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None


def test_baseline_valid_manifest_is_a_hit(repo_root, valid_manifest):
    _write_manifest(repo_root, valid_manifest)
    result = provenance_checker.check_sealed_provenance(SEALED_ID, repo_root)
    assert _get(result, "hit") is True
    assert _get(result, "reason") is None
    assert _get(result, "sealed") is True


@pytest.mark.parametrize("raw", ["[]", "5", '"a string"', "null"])
def test_manifest_not_an_object_is_invalid(repo_root, valid_manifest, raw):
    _write_manifest_text(repo_root, raw)
    result = provenance_checker.check_sealed_provenance(SEALED_ID, repo_root)
    _assert_miss(result, "manifest_invalid")


FIELD_INVALID_CASES = [
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


@pytest.mark.parametrize("field,value", FIELD_INVALID_CASES)
def test_single_field_mutation_is_invalid(repo_root, valid_manifest, field, value):
    manifest = dict(valid_manifest)
    manifest[field] = value
    _write_manifest(repo_root, manifest)
    result = provenance_checker.check_sealed_provenance(SEALED_ID, repo_root)
    _assert_miss(result, "manifest_invalid")


CHARACTERIZATION_INVALID_CASES = [
    [],
    {"overall": "pass", "criteria_passed": 3},
    {"overall": "pass", "criteria_passed": 3, "criteria_total": 3, "extra": 1},
    {"overall": "ok", "criteria_passed": 3, "criteria_total": 3},
    {"overall": 5, "criteria_passed": 3, "criteria_total": 3},
    {"overall": "pass", "criteria_passed": "2", "criteria_total": 3},
    {"overall": "pass", "criteria_passed": True, "criteria_total": 3},
    {"overall": "pass", "criteria_passed": 3, "criteria_total": -1},
    {"overall": "pass", "criteria_passed": 3, "criteria_total": 2},
    {"overall": "pass", "criteria_passed": 0, "criteria_total": 0},
]


@pytest.mark.parametrize("characterization", CHARACTERIZATION_INVALID_CASES)
def test_characterization_mutation_is_invalid(repo_root, valid_manifest, characterization):
    manifest = dict(valid_manifest)
    manifest["characterization"] = characterization
    _write_manifest(repo_root, manifest)
    result = provenance_checker.check_sealed_provenance(SEALED_ID, repo_root)
    _assert_miss(result, "manifest_invalid")


@pytest.mark.parametrize(
    "characterization",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
)
def test_failed_characterization_is_characterization_failed(
    repo_root, valid_manifest, characterization
):
    manifest = dict(valid_manifest)
    manifest["characterization"] = characterization
    _write_manifest(repo_root, manifest)
    result = provenance_checker.check_sealed_provenance(SEALED_ID, repo_root)
    _assert_miss(result, "characterization_failed")


def test_not_sealed_component(repo_root):
    _write_unsealed_component(repo_root)
    result = provenance_checker.check_sealed_provenance(UNSEALED_ID, repo_root)
    assert _get(result, "reason") == "not_sealed"
    assert _get(result, "sealed") is False
    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None