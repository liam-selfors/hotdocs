# hotdocs-criterion: sha256:fd05d86a53ddd82d32ca30e754499ba16af4b4ac97a11d4325b07f4987e438fc
import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64

PYTHON_ADAPTER_SRC = (
    "KIND = " + repr("python") + "\n"
    "\n"
    "def guidance():\n"
    "    return {" + repr("generator") + ": " + repr("") + ", "
    + repr("test_author") + ": " + repr("") + "}\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {" + repr("ok") + ": True, " + repr("reason") + ": " + repr("") + ", "
    + repr("versions") + ": {" + repr("python") + ": " + repr("3.12.4") + ", "
    + repr("packages") + ": " + repr(PK) + "}, "
    + repr("lockfile_sha256") + ": None, "
    + repr("interpreter") + ": " + repr("/fake/python") + "}\n"
)

VERIFIER_SRC = (
    "GATE_VERSION = " + repr("verifier-orchestrator@2.0.0") + "\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "class VerificationReport:\n"
    "    def __init__(self, component_id, criteria, requirement_results, interface_drift,\n"
    "                 mutation_score, mutation_error, assets, overall):\n"
    "        self.component_id = component_id\n"
    "        self.criteria = criteria\n"
    "        self.requirement_results = requirement_results\n"
    "        self.interface_drift = interface_drift\n"
    "        self.mutation_score = mutation_score\n"
    "        self.mutation_error = mutation_error\n"
    "        self.assets = assets\n"
    "        self.overall = overall\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {\n"
    "            " + repr("component_id") + ": self.component_id,\n"
    "            " + repr("criteria") + ": self.criteria,\n"
    "            " + repr("requirement_results") + ": self.requirement_results,\n"
    "            " + repr("interface_drift") + ": self.interface_drift,\n"
    "            " + repr("mutation_score") + ": self.mutation_score,\n"
    "            " + repr("mutation_error") + ": self.mutation_error,\n"
    "            " + repr("assets") + ": self.assets,\n"
    "            " + repr("overall") + ": self.overall,\n"
    "        }\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    return VerificationReport(component_id, [], {}, False, None, None, [], "
    + repr("pass") + ")\n"
)


def component_md(sealed):
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team, alice]\n"
        "depends_on: []\n"
    )
    if sealed:
        text += "sealed: true\n"
    text += (
        "source_path: pipeline/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    return text


def build_repo(repo_root, sealed=True):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(component_md(sealed))

    src_dir = repo_root / "pipeline" / "foo"
    src_dir.mkdir(parents=True)
    (src_dir / "foo.py").write_text("def foo():\n    return 1\n")

    vo_dir = repo_root / "gen" / "verifier-orchestrator"
    vo_dir.mkdir(parents=True)
    (vo_dir / "verifier_orchestrator.py").write_text(VERIFIER_SRC)

    kp_dir = repo_root / "gen" / "kind-python"
    kp_dir.mkdir(parents=True)
    (kp_dir / "kind_python.py").write_text(PYTHON_ADAPTER_SRC)


def valid_manifest(source_hash):
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


def manifest_path(repo_root):
    return repo_root / "pipeline" / "foo" / ".sealed-provenance.json"


def snapshot(repo_root):
    files = {}
    dirs = set()
    for dirpath, dirnames, filenames in os.walk(str(repo_root)):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        rel_dir = os.path.relpath(dirpath, str(repo_root))
        dirs.add(rel_dir)
        for name in filenames:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                files[os.path.relpath(full, str(repo_root))] = fh.read()
    return files, dirs


def other_hash():
    return "sha256:" + hashlib.sha256(b"some entirely different content\n").hexdigest()


def m_extra_key(m):
    m["extra"] = "x"
    return m


def m_lacks_key(m):
    del m["written_at"]
    return m


def m_version_true(m):
    m["version"] = True
    return m


def m_short_hash(m):
    m["source_hash"] = "sha256:abc"
    return m


def m_owner_upper(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def m_pass_partial(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


def m_not_json(m):
    return "{this is not json"


def m_comp_bar(m):
    m["component_id"] = "comp-bar"
    return m


def m_other_path(m):
    m["source_path"] = "pipeline/other/"
    return m


def m_source_changed(m):
    m["source_hash"] = other_hash()
    return m


def m_owners_only_team(m):
    m["owners"] = ["pipeline-team"]
    return m


def m_owners_reordered(m):
    m["owners"] = ["alice", "pipeline-team"]
    return m


def m_verifier_changed(m):
    m["verifier_version"] = "verifier-orchestrator@1.0.0"
    return m


def m_char_failed(m):
    m["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    return m


MISS_CASES = [
    ("not_json", m_not_json, "manifest_invalid"),
    ("extra_key", m_extra_key, "manifest_invalid"),
    ("lacks_key", m_lacks_key, "manifest_invalid"),
    ("version_true", m_version_true, "manifest_invalid"),
    ("short_hash", m_short_hash, "manifest_invalid"),
    ("owner_upper", m_owner_upper, "manifest_invalid"),
    ("pass_partial", m_pass_partial, "manifest_invalid"),
    ("comp_bar", m_comp_bar, "component_mismatch"),
    ("other_path", m_other_path, "component_mismatch"),
    ("source_changed", m_source_changed, "source_changed"),
    ("owners_only_team", m_owners_only_team, "owners_changed"),
    ("owners_reordered", m_owners_reordered, "owners_changed"),
    ("verifier_changed", m_verifier_changed, "verifier_changed"),
    ("char_failed", m_char_failed, "characterization_failed"),
]


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


def write_manifest(repo_root, content):
    if isinstance(content, str):
        manifest_path(repo_root).write_text(content)
    else:
        manifest_path(repo_root).write_text(json.dumps(content, indent=2))


def current_hash(repo_root):
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    return field(key, "source_hash")


def test_valid_current_manifest_hits(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    manifest = valid_manifest(current_hash(repo_root))
    write_manifest(repo_root, manifest)

    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)
    after = snapshot(repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert field(result, "verification_report") == {"overall": "pass"}
    assert field(result, "owners") == ["pipeline-team", "alice"]
    assert field(result, "written_at") == "2026-11-02T00:00:00Z"
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert before == after


def test_manifest_missing(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    assert not manifest_path(repo_root).exists()

    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)
    after = snapshot(repo_root)

    assert_miss(result, "manifest_missing")
    assert before == after


@pytest.mark.parametrize("name,mutate,reason", MISS_CASES, ids=[c[0] for c in MISS_CASES])
def test_manifest_miss_reasons(tmp_path, name, mutate, reason):
    repo_root = tmp_path / "repo"
    build_repo(repo_root)
    manifest = mutate(valid_manifest(current_hash(repo_root)))
    write_manifest(repo_root, manifest)

    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)
    after = snapshot(repo_root)

    assert_miss(result, reason)
    assert before == after


def test_not_sealed(tmp_path):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, sealed=False)
    assert provenance_checker.current_sealed_key("comp-foo", repo_root) is None
    write_manifest(repo_root, valid_manifest(other_hash()))

    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)
    after = snapshot(repo_root)

    assert_miss(result, "not_sealed", sealed=False)
    assert before == after