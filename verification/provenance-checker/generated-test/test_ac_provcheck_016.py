# hotdocs-criterion: sha256:c5f29ddb530c1d1a7fc8ed92b53591498616996c75d77abf02171acaeae313f9
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64
S = "sha256:" + "3" * 64
S2 = "sha256:" + "4" * 64
D = "sha256:" + "5" * 64
D2 = "sha256:" + "6" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _python_adapter_source():
    result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    return (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(result) + "\n"
    )


def _fake_adapter_source():
    result = {
        "ok": True,
        "reason": "",
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    return (
        "KIND = " + repr("fake") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "G.", "test_author": "T."}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(result) + "\n"
    )


def build_repo(repo_root, with_parts=True):
    repo_root = Path(repo_root)
    py_adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(py_adapter, _python_adapter_source())

    fake_def = repo_root / "specs" / "architecture" / "asset-kind-fake.md"
    _write(fake_def, "# Asset kind: fake\n\nA fixed fake asset kind definition.\n")

    fake_adapter = repo_root / "gen" / "kind-fake" / "kind_fake.py"
    _write(fake_adapter, _fake_adapter_source())

    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "assets: [fake:static/a.fake]\n"
        "---\n"
        "\n"
        "# Foo\n"
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    P = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha256_file(py_adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    fake_entry = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": sha256_file(fake_def),
        "adapter_sha256": sha256_file(fake_adapter),
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    E = [P, fake_entry]

    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": E,
        "drivers": [],
    }
    if with_parts:
        manifest["spec_bundle_parts"] = {"spec": S, "dependency_code": D}
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))
    return repo_root


@pytest.fixture
def repo_root(tmp_path):
    return build_repo(tmp_path / "repo", with_parts=True)


def test_dependency_code_differs_when_only_dependency_code_differs(repo_root):
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {}, repo_root, {"spec": S, "dependency_code": D2}
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "dependency code differs"


def test_spec_differs_keeps_spec_bundle_hash_reason(repo_root):
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {}, repo_root, {"spec": S2, "dependency_code": D2}
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_no_parts_given_keeps_spec_bundle_hash_reason(repo_root):
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {}, repo_root, None
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_manifest_without_parts_keeps_spec_bundle_hash_reason(tmp_path):
    root = build_repo(tmp_path / "repo_noparts", with_parts=False)
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {}, root, {"spec": S, "dependency_code": D2}
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_gate_versions_differ_keeps_spec_bundle_hash_reason(repo_root):
    result = provenance_checker.check_provenance(
        "comp-foo", H2, {"verifier": "v@1"}, repo_root,
        {"spec": S, "dependency_code": D2},
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_matching_hash_hits_despite_parts_difference(repo_root):
    result = provenance_checker.check_provenance(
        "comp-foo", H, {}, repo_root, {"spec": S, "dependency_code": D2}
    )
    assert field(result, "hit") is True
    assert field(result, "reason") is None