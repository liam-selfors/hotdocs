# hotdocs-criterion: sha256:bac5fc306521c69e7a803fb3d03cbb4a8e29c4aca29a91ee61adf41480b8e2e9
"""AC-PROVCHECK-006 (covers R-PROVCHECK-004): check_provenance is read-only.

Given gen/foo/.provenance.json exists
When check_provenance is called for comp-foo, on either a hit or a miss
Then the file's content and mtime are unchanged and no other file is written
"""

import json
import os
from pathlib import Path

import pytest

import provenance_checker


MATCHING_HASH = "sha256:" + "ab" * 32
OTHER_HASH = "sha256:" + "cd" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _manifest():
    return {
        "spec_bundle_hash": MATCHING_HASH,
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
            "mutation_score": 0.92,
            "mutation_error": None,
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


def _snapshot(root):
    """Map every path under root (files and directories) to its state."""
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        st = os.stat(d)
        state[str(d)] = ("dir", st.st_mtime_ns, tuple(sorted(dirnames + filenames)))
        for name in filenames:
            p = d / name
            st = os.stat(p)
            state[str(p)] = ("file", st.st_mtime_ns, st.st_size, p.read_bytes())
    return state


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True)
    ver_foo = repo_root / "verification" / "foo"
    ver_foo.mkdir(parents=True)

    text = json.dumps(_manifest(), indent=2, sort_keys=True) + "\n"
    manifest_path = gen_foo / ".provenance.json"
    manifest_path.write_text(text, encoding="utf-8")
    (ver_foo / ".provenance.json").write_text(text, encoding="utf-8")

    # Push mtimes into the past so any rewrite is visible even at coarse
    # filesystem timestamp resolution.
    past = 1_600_000_000
    for p in (manifest_path, ver_foo / ".provenance.json"):
        os.utime(p, (past, past))

    # Run with the workspace as cwd so any relative-path write lands where
    # the snapshot can see it.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    return tmp_path, repo_root, manifest_path, text.encode("utf-8")


def _assert_unchanged(before, after, manifest_path, original_bytes, past_mtime_ns):
    assert manifest_path.read_bytes() == original_bytes
    assert os.stat(manifest_path).st_mtime_ns == past_mtime_ns
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    assert added == [], "files written: " + repr(added)
    assert removed == [], "files deleted: " + repr(removed)
    changed = sorted(k for k in before if before[k] != after[k])
    assert changed == [], "paths modified: " + repr(changed)


def test_check_provenance_hit_attempt_is_read_only(workspace):
    root, repo_root, manifest_path, original = workspace
    past_ns = os.stat(manifest_path).st_mtime_ns
    before = _snapshot(root)

    result = provenance_checker.check_provenance(
        "comp-foo", MATCHING_HASH, dict(GATE_VERSIONS), repo_root
    )
    assert field(result, "hit") in (True, False)

    after = _snapshot(root)
    _assert_unchanged(before, after, manifest_path, original, past_ns)


def test_check_provenance_miss_is_read_only(workspace):
    root, repo_root, manifest_path, original = workspace
    past_ns = os.stat(manifest_path).st_mtime_ns
    before = _snapshot(root)

    result = provenance_checker.check_provenance(
        "comp-foo", OTHER_HASH, dict(GATE_VERSIONS), repo_root
    )
    assert field(result, "hit") is False

    after = _snapshot(root)
    _assert_unchanged(before, after, manifest_path, original, past_ns)


def test_check_provenance_gate_version_miss_is_read_only(workspace):
    root, repo_root, manifest_path, original = workspace
    past_ns = os.stat(manifest_path).st_mtime_ns
    before = _snapshot(root)

    changed = dict(GATE_VERSIONS)
    changed["compiler"] = "criterion-compiler@9.9.9"
    result = provenance_checker.check_provenance(
        "comp-foo", MATCHING_HASH, changed, repo_root
    )
    assert field(result, "hit") is False

    after = _snapshot(root)
    _assert_unchanged(before, after, manifest_path, original, past_ns)