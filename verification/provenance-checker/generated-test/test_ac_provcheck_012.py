# hotdocs-criterion: sha256:2e09243fd320152d555665e33b3daef9274a8052a1837004f3e0064272608023
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT = "2026-11-02T00:00:00Z"
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_python_adapter_source():
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    return (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def _fake_verifier_source():
    report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }
    return (
        "GATE_VERSION = " + repr(VERIFIER_VERSION) + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "class _Report(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "    def to_dict(self):\n"
        "        return dict(self)\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    report = " + repr(report) + "\n"
        "    report['component_id'] = component_id\n"
        "    return _Report(report)\n"
    )


def make_repo(tmp_path, sealed=True):
    root = tmp_path / "repo"
    root.mkdir()
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
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    _write(root / "specs" / "components" / "foo" / "component.md", "\n".join(lines) + "\n")
    _write(root / "pipeline" / "foo" / "foo.py", "def foo():\n    return 1\n")
    _write(
        root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _fake_verifier_source(),
    )
    _write(root / "gen" / "kind-python" / "kind_python.py", _fake_python_adapter_source())
    return root


def valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": source_hash,
        "verifier_version": VERIFIER_VERSION,
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": WRITTEN_AT,
    }


def manifest_path(root):
    return root / "pipeline" / "foo" / ".sealed-provenance.json"


def write_manifest(root, content):
    if content is None:
        return
    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content)
    _write(manifest_path(root), text)


def snapshot(root):
    snap = {}
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_dir():
            snap[rel.as_posix()] = None
        else:
            snap[rel.as_posix()] = p.read_bytes()
    return snap


def current_source_hash(root):
    key = provenance_checker.current_sealed_key("comp-foo", root)
    assert key is not None
    return field(key, "source_hash")


def run_check(root):
    before = snapshot(root)
    result = provenance_checker.check_sealed_provenance("comp-foo", root)
    after = snapshot(root)
    assert after == before, "check_sealed_provenance changed files under repo_root"
    return result


# ---- valid, current manifest -------------------------------------------------

def test_valid_current_manifest_hits(tmp_path):
    root = make_repo(tmp_path)
    write_manifest(root, valid_manifest(current_source_hash(root)))

    result = run_check(root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert field(result, "verification_report") == {"overall": "pass"}
    assert field(result, "owners") == OWNERS
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


# ---- manifest missing ---------------------------------------------------------

def test_manifest_missing(tmp_path):
    root = make_repo(tmp_path)
    current_source_hash(root)

    result = run_check(root)

    assert field(result, "reason") == "manifest_missing"
    assert field(result, "hit") is False


# ---- invalid manifests --------------------------------------------------------

def _not_json(m):
    return "this is { not json"


def _extra_key(m):
    m["extra"] = 1
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


def _bad_owner(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def _pass_not_all(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


@pytest.mark.parametrize(
    "mutate",
    [_not_json, _extra_key, _lacks_key, _version_true, _short_hash, _bad_owner, _pass_not_all],
    ids=["not-json", "extra-key", "lacks-key", "version-true", "short-hash", "owner-Alice", "pass-1-of-2"],
)
def test_manifest_invalid(tmp_path, mutate):
    root = make_repo(tmp_path)
    write_manifest(root, mutate(valid_manifest(current_source_hash(root))))

    result = run_check(root)

    assert field(result, "reason") == "manifest_invalid"
    assert field(result, "hit") is False
    assert field(result, "owners") is None
    assert field(result, "verification_report") is None


# ---- stale manifests ------------------------------------------------------------

def _other_component(m):
    m["component_id"] = "comp-bar"
    return m


def _other_source_path(m):
    m["source_path"] = "pipeline/other/"
    return m


def _different_hash(m):
    m["source_hash"] = "sha256:" + hashlib.sha256(b"different content entirely\n").hexdigest()
    return m


def _owners_one(m):
    m["owners"] = ["pipeline-team"]
    return m


def _owners_reordered(m):
    m["owners"] = ["alice", "pipeline-team"]
    return m


def _old_verifier(m):
    m["verifier_version"] = "verifier-orchestrator@1.0.0"
    return m


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (_other_component, "component_mismatch"),
        (_other_source_path, "component_mismatch"),
        (_different_hash, "source_changed"),
        (_owners_one, "owners_changed"),
        (_owners_reordered, "owners_changed"),
        (_old_verifier, "verifier_changed"),
    ],
    ids=["comp-bar", "other-source-path", "source-changed", "owners-one", "owners-reordered", "verifier-changed"],
)
def test_stale_manifest_reasons(tmp_path, mutate, expected):
    root = make_repo(tmp_path)
    source_hash = current_source_hash(root)
    manifest = mutate(valid_manifest(source_hash))
    if mutate is _different_hash:
        assert manifest["source_hash"] != source_hash
    write_manifest(root, manifest)

    result = run_check(root)

    assert field(result, "reason") == expected
    assert field(result, "hit") is False


# ---- characterization failed ----------------------------------------------------

def test_characterization_failed(tmp_path):
    root = make_repo(tmp_path)
    manifest = valid_manifest(current_source_hash(root))
    manifest["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    write_manifest(root, manifest)

    result = run_check(root)

    assert field(result, "reason") == "characterization_failed"
    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None


# ---- not sealed -------------------------------------------------------------------

def test_not_sealed(tmp_path):
    root = make_repo(tmp_path, sealed=False)
    assert provenance_checker.current_sealed_key("comp-foo", root) is None
    write_manifest(root, valid_manifest("sha256:" + "0" * 64))

    result = run_check(root)

    assert field(result, "reason") == "not_sealed"
    assert field(result, "hit") is False