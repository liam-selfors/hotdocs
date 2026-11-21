# hotdocs-criterion: sha256:1de75ea2c354b8bcdde5feb121a6b6f213521855727e6d50733add20c16b0432
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


H = "sha256:" + "1" * 64
PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def _write_manifest(repo_root, adapter_path):
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(adapter_path),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    adapter_path = _write_python_adapter(root)
    _write_component_md(root)
    _write_manifest(root, adapter_path)
    return root


@pytest.mark.parametrize(
    "other_hash",
    [
        "sha256:" + "2" * 64,
        "sha256:abc",
        H + "0",
    ],
)
def test_different_spec_bundle_hash_is_definitive_miss(repo_root, other_hash):
    assert other_hash != H

    result = provenance_checker.check_provenance("comp-foo", other_hash, {}, repo_root)

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None