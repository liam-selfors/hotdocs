# hotdocs-criterion: sha256:f523658a3ffefa3326734c5396f164453d7ca682aa894a510ca73958f705f254
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

STORED_HASH = "sha256:" + "1" * 64
OTHER_HASH = "sha256:" + "2" * 64


def _write_python_adapter(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    path.write_text(source, encoding="utf-8")
    return path


def _write_component(repo_root):
    path = repo_root / "specs" / "components" / "foo" / "component.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )


def _write_manifest(repo_root, python_entry):
    path = repo_root / "gen" / "foo" / ".provenance.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": STORED_HASH,
        "gate_versions": dict(GATE_VERSIONS),
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_ac_provcheck_002_spec_bundle_hash_mismatch_is_definitive_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _write_python_adapter(repo_root)
    _write_component(repo_root)
    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _write_manifest(repo_root, python_entry)

    assert OTHER_HASH != STORED_HASH

    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None