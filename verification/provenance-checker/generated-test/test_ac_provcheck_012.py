import contextlib
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_text(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team, alice]\n"
        "sealed: true\n"
        "source_path: pipeline/foo/\n"
        "---\n\n"
        "# Foo\n\n"
        "Purpose: fixture sealed component for provenance checker tests.\n",
    )

    _write_text(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# Bar\n\n"
        "Purpose: fixture non-sealed component for provenance checker tests.\n",
    )

    _write_text(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        'GATE_VERSION = "verifier-orchestrator@2.0.0"\n',
    )

    _write_text(
        repo_root / "pipeline" / "foo" / "foo.py",
        "def foo():\n    return 42\n",
    )

    return repo_root


@pytest.fixture
def sealed_repo(tmp_path):
    return _setup_repo(tmp_path)


def _valid_manifest(key):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": list(_get(key, "owners")),
        "source_path": _get(key, "source_path"),
        "source_hash": _get(key, "source_hash"),
        "verifier_version": _get(key, "verifier_version"),
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": "2026-11-02T00:00:00Z",
    }


def _write_manifest(repo_root, source_path, manifest):
    path = Path(repo_root) / source_path.rstrip("/") / ".sealed-provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _snapshot(repo_root):
    repo_root = Path(repo_root)
    snap = {}
    for p in repo_root.rglob("*"):
        if "__pycache__" in p.parts:
            continue
        if p.is_file():
            rel = str(p.relative_to(repo_root))
            snap[rel] = (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
    return snap


@contextlib.contextmanager
def _assert_read_only(repo_root):
    before = _snapshot(repo_root)
    yield
    after = _snapshot(repo_root)
    assert after == before


def test_valid_current_manifest(sealed_repo):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    assert key is not None
    manifest = _valid_manifest(key)
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is True
    assert _get(result, "reason") is None
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") == {"overall": "pass"}
    assert _get(result, "owners") == manifest["owners"]
    assert _get(result, "written_at") == manifest["written_at"]
    assert _get(result, "license_scan") is None
    assert _get(result, "secret_scan") is None


def test_manifest_missing(sealed_repo):
    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "manifest_missing"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


def test_manifest_invalid_not_json(sealed_repo):
    path = Path(sealed_repo) / "pipeline" / "foo" / ".sealed-provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{this is not valid json", encoding="utf-8")

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "manifest_invalid"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


def _mutate_extra_key(m):
    m["extra_field"] = "unexpected"
    return m


def _mutate_missing_key(m):
    del m["written_at"]
    return m


def _mutate_version_bool(m):
    m["version"] = True
    return m


def _mutate_bad_source_hash(m):
    m["source_hash"] = "sha256:abc"
    return m


def _mutate_bad_owner(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def _mutate_overall_passed_mismatch(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


@pytest.mark.parametrize(
    "mutate",
    [
        _mutate_extra_key,
        _mutate_missing_key,
        _mutate_version_bool,
        _mutate_bad_source_hash,
        _mutate_bad_owner,
        _mutate_overall_passed_mismatch,
    ],
)
def test_manifest_invalid_shape(sealed_repo, mutate):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = mutate(_valid_manifest(key))
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "manifest_invalid"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


@pytest.mark.parametrize(
    "field,value",
    [("component_id", "comp-bar"), ("source_path", "pipeline/other/")],
)
def test_component_mismatch(sealed_repo, field, value):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = _valid_manifest(key)
    manifest[field] = value
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "component_mismatch"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


def test_source_changed(sealed_repo):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = _valid_manifest(key)
    other_hash = "sha256:" + ("f" * 64)
    if other_hash == manifest["source_hash"]:
        other_hash = "sha256:" + ("0" * 64)
    manifest["source_hash"] = other_hash
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "source_changed"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


@pytest.mark.parametrize("owners", [["pipeline-team"], ["alice", "pipeline-team"]])
def test_owners_changed(sealed_repo, owners):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = _valid_manifest(key)
    manifest["owners"] = owners
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "owners_changed"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


def test_verifier_changed(sealed_repo):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = _valid_manifest(key)
    manifest["verifier_version"] = "verifier-orchestrator@1.0.0"
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "verifier_changed"
    assert _get(result, "sealed") is True
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None


def test_characterization_failed(sealed_repo):
    key = provenance_checker.current_sealed_key("comp-foo", sealed_repo)
    manifest = _valid_manifest(key)
    manifest["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    _write_manifest(sealed_repo, "pipeline/foo/", manifest)

    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-foo", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "characterization_failed"
    assert _get(result, "sealed") is True
    assert _get(result, "verification_report") is None
    assert _get(result, "owners") is None
    assert _get(result, "source_hash") is None
    assert _get(result, "written_at") is None


def test_not_sealed(sealed_repo):
    with _assert_read_only(sealed_repo):
        result = provenance_checker.check_sealed_provenance("comp-bar", sealed_repo)

    assert _get(result, "hit") is False
    assert _get(result, "reason") == "not_sealed"
    assert _get(result, "sealed") is False
    assert _get(result, "owners") is None
    assert _get(result, "verification_report") is None