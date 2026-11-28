# hotdocs-criterion: sha256:3a1ca2ab13e51bc7bc3624f29b837a0b109446742a3bb8e9d7480436d8d6ff1f
import hashlib
import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "1" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _python_adapter_source():
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
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def _build_repo(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    adapter_path = adapter_dir / "kind_python.py"
    adapter_path.write_text(_python_adapter_source(), encoding="utf-8")
    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()

    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
        encoding="utf-8",
    )

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {"license_scanner": "1.0.0"},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True)
    (gen_foo / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_ac_provcheck_008_gate_version_mismatch_is_miss_even_with_matching_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "2.0.0"}, repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "reason") in ("gates differ", "gate_versions differ")
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None

    # Control: the very same manifest hits when gate_versions also match,
    # so the miss above is due to gate_versions alone.
    control = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "1.0.0"}, repo_root
    )
    assert field(control, "hit") is True
    assert field(control, "reason") is None