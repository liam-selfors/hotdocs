# hotdocs-criterion: sha256:86d121eed30d88e085a4f03ee2bedbaaf59dfcfc9700ca02106ca091774fcc16
import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
SOURCE_PATH = "pipeline/foo/"
OWNERS = ["pipeline-team", "alice"]
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT = "2026-11-02T00:00:00Z"
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, sealed=True):
    lines = [
        "---",
        "id: " + COMPONENT_ID,
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team, alice]",
        "depends_on: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: " + SOURCE_PATH)
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A fixture component.")
    lines.append("")
    write(repo_root / "specs" / "components" / "foo" / "component.md", "\n".join(lines))

    write(
        repo_root / "pipeline" / "foo" / "foo.py",
        "def foo():\n    return " + repr("foo") + "\n",
    )

    write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr(VERIFIER_VERSION) + "\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    raise RuntimeError(" + repr("verify must not be called") + ")\n",
    )

    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "KIND = " + repr("python") + "\n"
        + "\n"
        + "def guidance():\n"
        + "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        + "\n"
        + "def provision(repo_root):\n"
        + "    return " + repr(provision_result) + "\n",
    )


def valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": source_hash,
        "verifier_version": VERIFIER_VERSION,
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": WRITTEN_AT,
    }


def manifest_path(repo_root):
    return repo_root / "pipeline" / "foo" / ".sealed-provenance.json"


def write_manifest(repo_root, manifest):
    if isinstance(manifest, str):
        text = manifest
    else:
        text = json.dumps(manifest, indent=2)
    write(manifest_path(repo_root), text)


def snapshot(repo_root):
    result = {}
    for p in sorted(repo_root.rglob("*")):
        rel = p.relative_to(repo_root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            result[rel.as_posix()] = p.read_bytes()
    return result


def current_source_hash(repo_root):
    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None
    return field(key, "source_hash")


def run_check(repo_root):
    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = snapshot(repo_root)
    assert before == after, "check_sealed_provenance changed files under repo_root"
    return result


def assert_miss(result, reason, sealed=True):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is sealed
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_valid_current_manifest_hits(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    write_manifest(repo_root, valid_manifest(source_hash))

    result = run_check(repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert field(result, "verification_report") == {"overall": "pass"}
    assert field(result, "owners") == ["pipeline-team", "alice"]
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_manifest_missing(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    current_source_hash(repo_root)
    assert not manifest_path(repo_root).exists()

    result = run_check(repo_root)

    assert_miss(result, "manifest_missing")


def _not_json(m):
    return "{this is not json"


def _extra_key(m):
    m["extra"] = "x"
    return m


def _lacks_key(m):
    del m["written_at"]
    return m


def _version_true(m):
    m["version"] = True
    return m


def _short_hash(m):
    m["source_hash"] = "sha256:abc"
    return m


def _owner_capital(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def _pass_partial(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


@pytest.mark.parametrize(
    "mutate",
    [_not_json, _extra_key, _lacks_key, _version_true, _short_hash, _owner_capital, _pass_partial],
    ids=["not-json", "extra-key", "lacks-key", "version-true", "short-hash", "owner-Alice", "pass-1-of-2"],
)
def test_manifest_invalid(tmp_path, mutate):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    write_manifest(repo_root, mutate(copy.deepcopy(valid_manifest(source_hash))))

    result = run_check(repo_root)

    assert_miss(result, "manifest_invalid")


@pytest.mark.parametrize(
    "key,value",
    [("component_id", "comp-bar"), ("source_path", "pipeline/other/")],
    ids=["component-id", "source-path"],
)
def test_component_mismatch(tmp_path, key, value):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    manifest = valid_manifest(source_hash)
    manifest[key] = value
    write_manifest(repo_root, manifest)

    result = run_check(repo_root)

    assert_miss(result, "component_mismatch")


def test_source_changed(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    other = "sha256:" + hashlib.sha256(b"different content\n").hexdigest()
    assert other != source_hash
    manifest = valid_manifest(other)
    write_manifest(repo_root, manifest)

    result = run_check(repo_root)

    assert_miss(result, "source_changed")


@pytest.mark.parametrize(
    "owners",
    [["pipeline-team"], ["alice", "pipeline-team"]],
    ids=["subset", "reordered"],
)
def test_owners_changed(tmp_path, owners):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    manifest = valid_manifest(source_hash)
    manifest["owners"] = owners
    write_manifest(repo_root, manifest)

    result = run_check(repo_root)

    assert_miss(result, "owners_changed")


def test_verifier_changed(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    manifest = valid_manifest(source_hash)
    manifest["verifier_version"] = "verifier-orchestrator@1.0.0"
    write_manifest(repo_root, manifest)

    result = run_check(repo_root)

    assert_miss(result, "verifier_changed")


def test_characterization_failed(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    source_hash = current_source_hash(repo_root)
    manifest = valid_manifest(source_hash)
    manifest["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    write_manifest(repo_root, manifest)

    result = run_check(repo_root)

    assert_miss(result, "characterization_failed")


def test_not_sealed(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, sealed=False)
    assert provenance_checker.current_sealed_key(COMPONENT_ID, repo_root) is None
    write_manifest(repo_root, valid_manifest("sha256:" + "0" * 64))

    result = run_check(repo_root)

    assert_miss(result, "not_sealed", sealed=False)