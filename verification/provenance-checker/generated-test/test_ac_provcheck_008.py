# hotdocs-criterion: sha256:3d132566fbc81111fcd96884641da0f9a999c6af54d23acc98d4f8c72bcc15e7
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "0123456789abcdef" * 4


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
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(path, source)
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _plant_component(repo_root):
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", text)


def _plant_manifest(repo_root, gate_versions, assets):
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": gate_versions,
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
        "drivers": [],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))


def test_ac_provcheck_008_gate_version_mismatch_is_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    pa = _plant_python_adapter(repo_root)
    _plant_component(repo_root)
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _plant_manifest(repo_root, {"license_scanner": "1.0.0"}, [p_entry])

    result = provenance_checker.check_provenance(
        "comp-foo",
        H,
        {"license_scanner": "2.0.0"},
        repo_root,
    )

    assert field(result, "hit") is False
    # The manifest exists and was read: the miss is not for want of one.
    assert field(result, "reason") != "no manifest"