import json
import os
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

OLD_MTIME_NS = 1_600_000_000_000_000_000  # fixed, well in the past


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest():
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
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "compiled",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        },
        "license_scan": {
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
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": GATE_VERSIONS["secret_scanner"],
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def _setup_repo(repo_root: Path) -> Path:
    content = json.dumps(_manifest(), indent=2, sort_keys=True) + "\n"
    gen_manifest = repo_root / "gen" / "foo" / ".provenance.json"
    gen_manifest.parent.mkdir(parents=True)
    gen_manifest.write_text(content, encoding="utf-8")
    ver_manifest = repo_root / "verification" / "foo" / ".provenance.json"
    ver_manifest.parent.mkdir(parents=True)
    ver_manifest.write_text(content, encoding="utf-8")
    for p in (gen_manifest, ver_manifest):
        os.utime(p, ns=(OLD_MTIME_NS, OLD_MTIME_NS))
    return gen_manifest


def _snapshot(repo_root: Path):
    files = {}
    dirs = set()
    for p in repo_root.rglob("*"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(repo_root).as_posix()
        if p.is_dir():
            dirs.add(rel)
        else:
            st = p.stat()
            files[rel] = (p.read_bytes(), st.st_mtime_ns)
    return files, dirs


def _assert_untouched(repo_root, gen_manifest, original_bytes, before):
    assert gen_manifest.is_file(), ".provenance.json was deleted"
    assert gen_manifest.read_bytes() == original_bytes, ".provenance.json content changed"
    assert gen_manifest.stat().st_mtime_ns == OLD_MTIME_NS, ".provenance.json mtime changed"
    after = _snapshot(repo_root)
    assert after[1] == before[1], "directories were created or removed"
    assert set(after[0]) == set(before[0]), (
        "files were created or deleted: "
        f"added={sorted(set(after[0]) - set(before[0]))}, "
        f"removed={sorted(set(before[0]) - set(after[0]))}"
    )
    for rel, (data, mtime) in before[0].items():
        assert after[0][rel][0] == data, f"{rel} content changed"
        assert after[0][rel][1] == mtime, f"{rel} mtime changed"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    monkeypatch.chdir(repo_root)
    gen_manifest = _setup_repo(repo_root)
    return repo_root, gen_manifest


def test_hit_is_read_only(repo):
    repo_root, gen_manifest = repo
    original = gen_manifest.read_bytes()
    before = _snapshot(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", SPEC_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is True
    _assert_untouched(repo_root, gen_manifest, original, before)


def test_miss_on_hash_mismatch_is_read_only(repo):
    repo_root, gen_manifest = repo
    original = gen_manifest.read_bytes()
    before = _snapshot(repo_root)

    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, dict(GATE_VERSIONS), repo_root
    )

    assert field(result, "hit") is False
    _assert_untouched(repo_root, gen_manifest, original, before)


def test_miss_on_gate_version_mismatch_is_read_only(repo):
    repo_root, gen_manifest = repo
    original = gen_manifest.read_bytes()
    before = _snapshot(repo_root)

    changed = dict(GATE_VERSIONS)
    changed["verifier"] = "verifier-orchestrator@9.9.9"
    result = provenance_checker.check_provenance(
        "comp-foo", SPEC_HASH, changed, repo_root
    )

    assert field(result, "hit") is False
    _assert_untouched(repo_root, gen_manifest, original, before)