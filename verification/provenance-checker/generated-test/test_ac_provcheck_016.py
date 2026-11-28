# hotdocs-criterion: sha256:de5d6c900c2c1a8dfbcccc6527d223cbfdf700d1439d00ddc82482be3b5970ca
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


PYTHON_ADAPTER_SRC = (
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
    }) + "\n"
)

FAKE_ADAPTER_SRC = (
    "KIND = " + repr("fake") + "\n"
    "\n"
    "def guidance():\n"
    "    return " + repr({"generator": "G.", "test_author": "T."}) + "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return " + repr({
        "ok": True,
        "reason": "",
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }) + "\n"
)

COMPONENT_MD = (
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
    "\n"
    "A fixture component.\n"
)

DEFAULT_PARTS = {"spec": "S", "dependency_code": "D"}


def build_repo(repo_root):
    py_adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    py_adapter.parent.mkdir(parents=True, exist_ok=True)
    py_adapter.write_text(PYTHON_ADAPTER_SRC)

    fake_adapter = repo_root / "gen" / "kind-fake" / "kind_fake.py"
    fake_adapter.parent.mkdir(parents=True, exist_ok=True)
    fake_adapter.write_text(FAKE_ADAPTER_SRC)

    definition = repo_root / "specs" / "architecture" / "asset-kind-fake.md"
    definition.parent.mkdir(parents=True, exist_ok=True)
    definition.write_text("# Asset kind fake\n\nA fixed fake definition.\n")

    component = repo_root / "specs" / "components" / "foo" / "component.md"
    component.parent.mkdir(parents=True, exist_ok=True)
    component.write_text(COMPONENT_MD)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha(py_adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    fake_entry = {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": sha(definition),
        "adapter_sha256": sha(fake_adapter),
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
    return [p_entry, fake_entry]


def write_manifest(repo_root, assets, parts=DEFAULT_PARTS):
    manifest = {
        "spec_bundle_hash": "H",
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
        "drivers": [],
    }
    if parts is not None:
        manifest["spec_bundle_parts"] = dict(parts)
    path = repo_root / "gen" / "foo" / ".provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2))


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    expected_assets = build_repo(repo_root)
    write_manifest(repo_root, expected_assets)
    return repo_root, expected_assets


def test_dependency_code_differs_when_only_dependency_code_changed(repo):
    repo_root, _ = repo
    result = provenance_checker.check_provenance(
        "comp-foo", "H2", {}, repo_root, {"spec": "S", "dependency_code": "D2"}
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "dependency code differs"


@pytest.mark.parametrize(
    "parts",
    [
        {"spec": "S2", "dependency_code": "D2"},
        None,
    ],
    ids=["spec-also-differs", "no-parts-given"],
)
def test_spec_bundle_hash_differs_when_parts_do_not_qualify(repo, parts):
    repo_root, _ = repo
    result = provenance_checker.check_provenance(
        "comp-foo", "H2", {}, repo_root, parts
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_spec_bundle_hash_differs_when_manifest_has_no_parts(repo):
    repo_root, expected_assets = repo
    write_manifest(repo_root, expected_assets, parts=None)
    result = provenance_checker.check_provenance(
        "comp-foo", "H2", {}, repo_root, {"spec": "S", "dependency_code": "D2"}
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_verifier_change_still_dependency_code_differs(repo):
    repo_root, _ = repo
    result = provenance_checker.check_provenance(
        "comp-foo",
        "H2",
        {"verifier": "v@1"},
        repo_root,
        {"spec": "S", "dependency_code": "D2"},
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "dependency code differs"


def test_generator_change_keeps_spec_bundle_hash_differs(repo):
    repo_root, _ = repo
    result = provenance_checker.check_provenance(
        "comp-foo",
        "H2",
        {"generator": "g@2"},
        repo_root,
        {"spec": "S", "dependency_code": "D2"},
    )
    assert field(result, "hit") is False
    assert field(result, "reason") == "spec_bundle_hash differs"


def test_matching_hash_hits_despite_differing_parts(repo):
    repo_root, _ = repo
    result = provenance_checker.check_provenance(
        "comp-foo", "H", {}, repo_root, {"spec": "S", "dependency_code": "D2"}
    )
    assert field(result, "hit") is True