# hotdocs-criterion: sha256:64bf9b7781504f7a79587f86250a52aac5b8a3e3718069e814279c6df0bfeac0
import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
MANIFEST_HASH = "sha256:" + "0123456789abcdef" * 4
OTHER_HASH = "sha256:" + "fedcba9876543210" * 4
OLD_TIME_NS = 1_000_000_000 * 1_000_000_000  # a fixed, old mtime (2001)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha256_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    src = (
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
    path = adapter_dir / "kind_python.py"
    path.write_text(src, encoding="utf-8")
    return path


def write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def write_manifest(repo_root, python_entry):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": MANIFEST_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    path = gen_dir / ".provenance.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.utime(path, ns=(OLD_TIME_NS, OLD_TIME_NS))
    return path


def build_repo(repo_root):
    adapter_path = write_python_adapter(repo_root)
    write_component_md(repo_root)
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha256_of(adapter_path),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    manifest_path = write_manifest(repo_root, python_entry)
    # Make every planted file's mtime old and fixed, so any rewrite shows.
    for p in repo_root.rglob("*"):
        if p.is_file():
            os.utime(p, ns=(OLD_TIME_NS, OLD_TIME_NS))
    return manifest_path


def snapshot(root):
    state = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        st = os.lstat(p)
        if p.is_dir() and not p.is_symlink():
            state[rel] = ("dir",)
        else:
            state[rel] = ("file", p.read_bytes(), st.st_mtime_ns)
    return state


@pytest.mark.parametrize(
    "case",
    ["hit", "miss-spec-bundle-hash", "miss-gate-versions"],
)
def test_check_provenance_is_read_only(tmp_path, case):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest_path = build_repo(repo_root)

    manifest_bytes_before = manifest_path.read_bytes()
    manifest_mtime_before = os.stat(manifest_path).st_mtime_ns
    before = snapshot(repo_root)

    if case == "hit":
        spec_hash, gate_versions = MANIFEST_HASH, {}
    elif case == "miss-spec-bundle-hash":
        spec_hash, gate_versions = OTHER_HASH, {}
    else:
        spec_hash, gate_versions = MANIFEST_HASH, {"compiler": "criterion-compiler@9.9.9"}

    result = provenance_checker.check_provenance(
        "comp-foo", spec_hash, gate_versions, repo_root
    )

    # The scenario really is a hit or a miss as intended.
    if case == "hit":
        assert field(result, "hit") is True, field(result, "reason")
    else:
        assert field(result, "hit") is False

    # The manifest's content and mtime are unchanged.
    assert manifest_path.is_file()
    assert manifest_path.read_bytes() == manifest_bytes_before
    assert os.stat(manifest_path).st_mtime_ns == manifest_mtime_before

    # No other file under repo_root was written, modified, created or deleted.
    after = snapshot(repo_root)
    assert set(after) == set(before), (
        "created: " + repr(sorted(set(after) - set(before)))
        + " deleted: " + repr(sorted(set(before) - set(after)))
    )
    for rel, entry in before.items():
        assert after[rel] == entry, "changed: " + rel