# hotdocs-criterion: sha256:389b2e3439828276d22116eb82b7e77f331cd7e1c283212ea6d475de5812ecac
import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PK = "sha256:" + "a" * 64
OLD_MTIME_NS = 1_600_000_000_000_000_000


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _kind_python_source():
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
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )


def _build_repo(repo_root):
    kind_python = repo_root / "gen" / "kind-python" / "kind_python.py"
    _write(kind_python, _kind_python_source())
    pa = "sha256:" + hashlib.sha256(kind_python.read_bytes()).hexdigest()

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
        "spec_bundle_hash": "sha256:abc",
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    _write(manifest_path, json.dumps(manifest, indent=2))
    os.utime(manifest_path, ns=(OLD_MTIME_NS, OLD_MTIME_NS))
    return manifest_path


def _snapshot(repo_root):
    files = {}
    dirs = set()
    for p in repo_root.rglob("*"):
        rel = p.relative_to(repo_root).as_posix()
        if p.is_dir():
            dirs.add(rel)
        else:
            st = p.stat()
            files[rel] = (p.read_bytes(), st.st_mtime_ns)
    return files, dirs


@pytest.mark.parametrize("scenario", ["hit", "miss"])
def test_check_provenance_is_read_only(tmp_path, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest_path = _build_repo(repo_root)

    before_bytes = manifest_path.read_bytes()
    before_mtime = manifest_path.stat().st_mtime_ns
    before_files, before_dirs = _snapshot(repo_root)

    if scenario == "hit":
        spec_bundle_hash = "sha256:abc"
    else:
        spec_bundle_hash = "sha256:def"

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, {}, repo_root
    )

    if scenario == "miss":
        assert field(result, "hit") is False

    assert manifest_path.read_bytes() == before_bytes
    assert manifest_path.stat().st_mtime_ns == before_mtime

    after_files, after_dirs = _snapshot(repo_root)
    assert set(after_files) == set(before_files), (
        "files added or removed: "
        + repr(sorted(set(after_files) ^ set(before_files)))
    )
    assert after_dirs == before_dirs, (
        "directories added or removed: " + repr(sorted(after_dirs ^ before_dirs))
    )
    for rel, (content, mtime) in before_files.items():
        assert after_files[rel][0] == content, rel + " content changed"
        assert after_files[rel][1] == mtime, rel + " mtime changed"