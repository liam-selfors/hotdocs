# hotdocs-criterion: sha256:7ded37c74d5349a692860bd957594973925327006f6deea3613a39fd214872a9
import hashlib
import json
from pathlib import Path

import provenance_checker


H = "sha256:" + "1" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
    path = adapter_dir / "kind_python.py"
    path.write_text(source, encoding="utf-8")
    return path


def _expected_python_entry(adapter_path):
    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }


def _write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
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
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _write_manifest(repo_root, gate_versions, assets):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": gate_versions,
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def _build_fixture(repo_root):
    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)
    p_entry = _expected_python_entry(adapter_path)
    _write_manifest(repo_root, {"license_scanner": "1.0.0"}, [p_entry])


def test_ac_provcheck_008_gate_version_change_is_miss_despite_matching_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "2.0.0"}, repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "reason") == "gate_versions differ"
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_ac_provcheck_008_control_matching_gate_versions_hits(tmp_path):
    # Same fixture with matching gate_versions hits, so the miss above is
    # caused by the gate version difference alone.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", H, {"license_scanner": "1.0.0"}, repo_root
    )

    assert field(result, "hit") is True
    assert field(result, "reason") is None