# hotdocs-criterion: sha256:1a87324a5c566f9a5c5badf648403496205c0cf05129345782553c71d59813ef
"""AC-PROVCHECK-006: check_provenance is read-only (R-PROVCHECK-004).

Given gen/foo/.provenance.json exists, when check_provenance is called for
comp-foo, on either a hit or a miss, the manifest's content and mtime are
unchanged and no other file is written.
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


FIXED_TIME_NS = 1_600_000_000 * 1_000_000_000
PK = "sha256:" + "a" * 64
MATCHING_HASH = "sha256:abc"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _python_adapter_source():
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    guidance_result = {"generator": "", "test_author": ""}
    return (
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


def _component_md():
    return (
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


def _build_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(_python_adapter_source(), encoding="utf-8")

    component_md = repo_root / "specs" / "components" / "foo" / "component.md"
    component_md.parent.mkdir(parents=True)
    component_md.write_text(_component_md(), encoding="utf-8")

    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(adapter),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest = {
        "spec_bundle_hash": MATCHING_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Pin every file's and directory's mtime to a fixed past time, so any
    # rewrite (even with identical bytes) or any entry created or removed
    # inside a directory is observable.
    for dirpath, dirnames, filenames in os.walk(repo_root, topdown=False):
        for name in filenames:
            os.utime(os.path.join(dirpath, name), ns=(FIXED_TIME_NS, FIXED_TIME_NS))
        os.utime(dirpath, ns=(FIXED_TIME_NS, FIXED_TIME_NS))

    return manifest_path


def _snapshot(repo_root):
    files = {}
    dirs = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = os.path.relpath(dirpath, repo_root)
        dirs[rel_dir] = os.stat(dirpath).st_mtime_ns
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, repo_root)
            with open(full, "rb") as handle:
                content = handle.read()
            files[rel] = (content, os.stat(full).st_mtime_ns)
    return files, dirs


@pytest.mark.parametrize(
    "spec_bundle_hash,gate_versions",
    [
        pytest.param(MATCHING_HASH, {}, id="hit"),
        pytest.param("sha256:def", {}, id="miss-spec-bundle-hash"),
        pytest.param(MATCHING_HASH, {"compiler": "cc@2"}, id="miss-gate-versions"),
    ],
)
def test_check_provenance_writes_nothing(tmp_path, spec_bundle_hash, gate_versions):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest_path = _build_repo(repo_root)

    manifest_bytes_before = manifest_path.read_bytes()
    manifest_mtime_before = os.stat(manifest_path).st_mtime_ns
    files_before, dirs_before = _snapshot(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", spec_bundle_hash, gate_versions, repo_root
    )

    # The call returned a result (hit or miss); its hit flag is a bool.
    assert isinstance(field(result, "hit"), bool)

    # The manifest itself is untouched: same content, same mtime.
    assert manifest_path.is_file()
    assert manifest_path.read_bytes() == manifest_bytes_before
    assert os.stat(manifest_path).st_mtime_ns == manifest_mtime_before

    # No other file was written, modified, created or deleted anywhere under
    # repo_root (a __pycache__ or any temporary file would show up here).
    files_after, dirs_after = _snapshot(repo_root)
    assert sorted(files_after) == sorted(files_before)
    for rel, (content, mtime) in files_before.items():
        assert files_after[rel][0] == content, rel
        assert files_after[rel][1] == mtime, rel
    assert sorted(dirs_after) == sorted(dirs_before)
    for rel, mtime in dirs_before.items():
        assert dirs_after[rel] == mtime, rel