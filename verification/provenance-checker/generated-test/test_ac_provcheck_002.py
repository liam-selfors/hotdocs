# hotdocs-criterion: sha256:766469b4f26f7c497aebb45e45a26c6edd6df2ca46472d03804461b53743e920
import hashlib
import json
from pathlib import Path

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant_python_adapter(repo_root):
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
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
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", text)


def test_spec_bundle_hash_mismatch_is_definitive_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    pa = _plant_python_adapter(repo_root)
    _plant_component(repo_root)

    stored_hash = "sha256:" + "1" * 64
    supplied_hash = "sha256:" + "2" * 64
    assert stored_hash != supplied_hash

    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": stored_hash,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest))

    result = provenance_checker.check_provenance(
        "comp-foo", supplied_hash, {}, repo_root
    )

    assert field(result, "hit") is False
    assert field(result, "verification_report") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None