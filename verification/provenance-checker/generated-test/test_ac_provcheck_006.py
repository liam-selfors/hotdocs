import json
import os
import sys
from pathlib import Path

import pytest

import provenance_checker


SPEC_HASH = "sha256:" + "ab" * 32
OTHER_HASH = "sha256:" + "cd" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

FIXED_MTIME = 1_600_000_000  # an old, fixed timestamp so any rewrite is visible


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest() -> dict:
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": GATE_VERSIONS["license_scanner"],
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": GATE_VERSIONS["secret_scanner"],
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "spec_bundle_hash": SPEC_HASH,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": dict(GATE_VERSIONS),
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }


def _build_repo(repo_root: Path) -> Path:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")

    manifest_text = json.dumps(_manifest(), indent=2, sort_keys=True) + "\n"
    gen_manifest = repo_root / "gen" / "foo" / ".provenance.json"
    _write(gen_manifest, manifest_text)
    _write(repo_root / "verification" / "foo" / ".provenance.json", manifest_text)

    # Pin every file's mtime to a fixed, old value so any rewrite is detectable.
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            os.utime(os.path.join(dirpath, name), (FIXED_MTIME, FIXED_MTIME))
    return gen_manifest


def _snapshot(root: Path):
    files = {}
    dirs = set()
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            dirs.add(os.path.relpath(os.path.join(dirpath, d), root))
        for name in filenames:
            full = os.path.join(dirpath, name)
            st = os.stat(full)
            with open(full, "rb") as fh:
                content = fh.read()
            files[os.path.relpath(full, root)] = (content, st.st_mtime_ns)
    return files, dirs


@pytest.mark.parametrize(
    "case",
    ["hit", "miss_spec_hash", "miss_gate_version"],
)
def test_check_provenance_is_read_only(tmp_path, monkeypatch, case):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gen_manifest = _build_repo(repo_root)
    # Run from inside repo_root so any cwd-relative write would also be caught.
    monkeypatch.chdir(repo_root)

    before_content = gen_manifest.read_bytes()
    before_mtime = gen_manifest.stat().st_mtime_ns
    before_files, before_dirs = _snapshot(repo_root)
    before_outside = sorted(os.listdir(tmp_path))

    gate_versions = dict(GATE_VERSIONS)
    spec_hash = SPEC_HASH
    if case == "miss_spec_hash":
        spec_hash = OTHER_HASH
    elif case == "miss_gate_version":
        gate_versions["compiler"] = "criterion-compiler@9.9.9"

    result = provenance_checker.check_provenance("comp-foo", spec_hash, gate_versions, repo_root)

    if case != "hit":
        assert field(result, "hit") is False

    # The manifest itself is untouched: same bytes, same mtime.
    assert gen_manifest.is_file()
    assert gen_manifest.read_bytes() == before_content
    assert gen_manifest.stat().st_mtime_ns == before_mtime

    # No other file anywhere under repo_root was written, modified, created or deleted.
    after_files, after_dirs = _snapshot(repo_root)
    assert set(after_files) == set(before_files)
    assert after_dirs == before_dirs
    for rel, (content, mtime) in before_files.items():
        assert after_files[rel][0] == content, f"{rel} content changed"
        assert after_files[rel][1] == mtime, f"{rel} mtime changed"

    # Nothing written beside repo_root either.
    assert sorted(os.listdir(tmp_path)) == before_outside


def test_check_provenance_hit_then_miss_leaves_tree_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gen_manifest = _build_repo(repo_root)
    monkeypatch.chdir(repo_root)

    before_content = gen_manifest.read_bytes()
    before_mtime = gen_manifest.stat().st_mtime_ns
    before = _snapshot(repo_root)

    provenance_checker.check_provenance("comp-foo", SPEC_HASH, dict(GATE_VERSIONS), repo_root)
    miss = provenance_checker.check_provenance("comp-foo", OTHER_HASH, dict(GATE_VERSIONS), repo_root)
    assert field(miss, "hit") is False

    assert gen_manifest.read_bytes() == before_content
    assert gen_manifest.stat().st_mtime_ns == before_mtime
    assert _snapshot(repo_root) == before