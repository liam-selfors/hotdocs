import json

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
NOT_SEALED_COMPONENT_ID = "comp-bar"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"

    _write(repo_root / "specs" / "components" / "foo" / "component.md", (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: fixture-src/\n"
        "last_ratified_commit: 0000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A sealed fixture component for AC-PROVCHECK-013.\n"
    ))

    _write(repo_root / "specs" / "components" / "bar" / "component.md", (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "sealed: false\n"
        "last_ratified_commit: 0000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A not-sealed fixture component for AC-PROVCHECK-013.\n"
    ))

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n',
    )

    _write(
        repo_root / "fixture-src" / "main.py",
        "def hello():\n    return 1\n",
    )

    return repo_root


def _manifest_path(repo_root):
    return repo_root / "fixture-src" / ".sealed-provenance.json"


def _write_manifest(repo_root, content):
    _write(_manifest_path(repo_root), content)


def _valid_manifest_dict(repo_root):
    # source_hash's exact algorithm is the target's own; read it back from
    # the real key rather than guessing, so the fixture manifest is genuinely current.
    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(_get(key, "owners")),
        "source_path": _get(key, "source_path"),
        "source_hash": _get(key, "source_hash"),
        "verifier_version": _get(key, "verifier_version"),
        "characterization": {"overall": "pass", "criteria_passed": 3, "criteria_total": 3},
        "written_at": "2026-11-02T00:00:00Z",
    }


def _check(repo_root, component_id=COMPONENT_ID):
    return provenance_checker.check_sealed_provenance(component_id, repo_root)


def test_valid_current_manifest_is_a_hit(tmp_path):
    repo_root = _setup_repo(tmp_path)
    manifest = _valid_manifest_dict(repo_root)
    _write_manifest(repo_root, json.dumps(manifest))

    result = _check(repo_root)

    assert _get(result, "reason") is None
    assert _get(result, "hit") is True
    assert _get(result, "sealed") is True
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


NOT_OBJECT_MANIFESTS = [
    json.dumps([1, 2, 3]),
    json.dumps(5),
    json.dumps("a string"),
    json.dumps(None),
]


@pytest.mark.parametrize("raw", NOT_OBJECT_MANIFESTS)
def test_manifest_not_an_object_is_invalid(tmp_path, raw):
    repo_root = _setup_repo(tmp_path)
    _write_manifest(repo_root, raw)

    result = _check(repo_root)

    assert _get(result, "reason") == "manifest_invalid"
    assert _get(result, "hit") is False
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


TOP_LEVEL_INVALID_CASES = [
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


@pytest.mark.parametrize("field,value", TOP_LEVEL_INVALID_CASES)
def test_top_level_field_invalid_value_is_manifest_invalid(tmp_path, field, value):
    repo_root = _setup_repo(tmp_path)
    manifest = _valid_manifest_dict(repo_root)
    manifest[field] = value
    _write_manifest(repo_root, json.dumps(manifest))

    result = _check(repo_root)

    assert _get(result, "reason") == "manifest_invalid"
    assert _get(result, "hit") is False
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


CHARACTERIZATION_INVALID_CASES = [
    [1, 2, 3],
    {"overall": "pass", "criteria_passed": 3},
    {"overall": "pass", "criteria_passed": 3, "criteria_total": 3, "extra": 1},
    {"overall": "ok", "criteria_passed": 3, "criteria_total": 3},
    {"overall": 5, "criteria_passed": 3, "criteria_total": 3},
    {"overall": "fail", "criteria_passed": "2", "criteria_total": 3},
    {"overall": "fail", "criteria_passed": True, "criteria_total": 3},
    {"overall": "fail", "criteria_passed": 0, "criteria_total": -1},
    {"overall": "fail", "criteria_passed": 3, "criteria_total": 2},
    {"overall": "pass", "criteria_passed": 0, "criteria_total": 0},
]


@pytest.mark.parametrize("characterization", CHARACTERIZATION_INVALID_CASES)
def test_characterization_invalid_is_manifest_invalid(tmp_path, characterization):
    repo_root = _setup_repo(tmp_path)
    manifest = _valid_manifest_dict(repo_root)
    manifest["characterization"] = characterization
    _write_manifest(repo_root, json.dumps(manifest))

    result = _check(repo_root)

    assert _get(result, "reason") == "manifest_invalid"
    assert _get(result, "hit") is False
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


CHARACTERIZATION_FAILED_CASES = [
    {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
    {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
]


@pytest.mark.parametrize("characterization", CHARACTERIZATION_FAILED_CASES)
def test_valid_manifest_with_failed_characterization(tmp_path, characterization):
    repo_root = _setup_repo(tmp_path)
    manifest = _valid_manifest_dict(repo_root)
    manifest["characterization"] = characterization
    _write_manifest(repo_root, json.dumps(manifest))

    result = _check(repo_root)

    assert _get(result, "reason") == "characterization_failed"
    assert _get(result, "hit") is False
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


def test_not_sealed_component_reports_not_sealed(tmp_path):
    repo_root = _setup_repo(tmp_path)

    result = _check(repo_root, component_id=NOT_SEALED_COMPONENT_ID)

    assert _get(result, "reason") == "not_sealed"
    assert _get(result, "sealed") is False
    assert _get(result, "hit") is False
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None