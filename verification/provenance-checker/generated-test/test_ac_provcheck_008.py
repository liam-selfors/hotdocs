# hotdocs-criterion: sha256:43763b1ce9a67e49b4d0a54a63da4dd13073a719d640dd1056e8578bbb3ebcb7
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
H = "sha256:" + "b" * 64


def _write_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    guidance_result = {"generator": "", "test_author": ""}
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr(guidance_result) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    path = adapter_dir / "kind_python.py"
    path.write_text(source, encoding="utf-8")
    return path


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


def test_gate_version_mismatch_is_a_miss_even_when_spec_bundle_hash_matches(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)

    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    python_entry = {
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
        "assets": [python_entry],
    }
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = provenance_checker.check_provenance(
        "comp-foo",
        H,
        {"license_scanner": "2.0.0"},
        Path(repo_root),
    )

    assert field(result, "hit") is False