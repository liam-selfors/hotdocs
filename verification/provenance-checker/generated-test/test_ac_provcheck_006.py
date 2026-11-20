# hotdocs-criterion: sha256:e38f342d13e91b93c40cdcd43e9f7f87a054d2287adc3e64034ad2b125760d2a
import hashlib
import json
import os
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
SPEC_HASH = "sha256:abc"
FIXED_TIME_NS = 1_600_000_000_000_000_000


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha256_file(path):
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


def write_component_md(repo_root):
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
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def write_manifest(repo_root, assets):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": SPEC_HASH,
        "gate_versions": {},
        "verification_report": {"criteria": []},
        "license_scan": {},
        "secret_scan": {},
        "assets": assets,
    }
    path = gen_dir / ".provenance.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def snapshot(root):
    """Map every file and directory under root to (kind, bytes, mtime_ns)."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = Path(dirpath) / d
            result[str(p.relative_to(root))] = ("dir", None, None)
        for f in filenames:
            p = Path(dirpath) / f
            st = p.stat()
            result[str(p.relative_to(root))] = ("file", p.read_bytes(), st.st_mtime_ns)
    return result


def set_fixed_mtimes(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for f in filenames:
            os.utime(Path(dirpath) / f, ns=(FIXED_TIME_NS, FIXED_TIME_NS))


@pytest.mark.parametrize("scenario", ["hit", "miss_spec_hash", "miss_assets"])
def test_check_provenance_is_read_only(tmp_path, monkeypatch, scenario):
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    outer = tmp_path
    repo_root = outer / "repo"
    repo_root.mkdir()

    adapter_path = write_python_adapter(repo_root)
    write_component_md(repo_root)

    pa = sha256_file(adapter_path)
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    if scenario == "miss_assets":
        manifest_assets = []
    else:
        manifest_assets = [p_entry]
    manifest_path = write_manifest(repo_root, manifest_assets)

    if scenario == "miss_spec_hash":
        call_hash = "sha256:def"
    else:
        call_hash = SPEC_HASH

    set_fixed_mtimes(outer)

    manifest_bytes_before = manifest_path.read_bytes()
    manifest_mtime_before = manifest_path.stat().st_mtime_ns
    before = snapshot(outer)

    result = provenance_checker.check_provenance("comp-foo", call_hash, {}, repo_root)

    hit = field(result, "hit")
    if scenario == "hit":
        assert hit is True
    else:
        assert hit is False

    # The manifest itself is untouched.
    assert manifest_path.is_file()
    assert manifest_path.read_bytes() == manifest_bytes_before
    assert manifest_path.stat().st_mtime_ns == manifest_mtime_before

    # No other file is written, modified, or deleted anywhere under the
    # temporary tree (no __pycache__, no .hotdocs/, nothing).
    after = snapshot(outer)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    assert added == [], "files/directories created: " + repr(added)
    assert removed == [], "files/directories removed: " + repr(removed)
    changed = sorted(k for k in before if before[k] != after[k])
    assert changed == [], "files modified: " + repr(changed)