import json
import os
import tempfile
import time
from pathlib import Path

import provenance_checker


def _write_manifest(path, spec_bundle_hash, gate_versions):
    manifest = {
        "spec_bundle_hash": spec_bundle_hash,
        "model_pin": "claude-sonnet-5",
        "prompt_version": "v1",
        "retry_feedback": None,
        "pipeline_version": "v1",
        "gate_versions": gate_versions,
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_run_id": "run-123",
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": "comp-foo",
            "gate_version": "license_scanner@4.0.0-no-reference-corpus",
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
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _snapshot(repo_root):
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            p = Path(dirpath) / name
            snap[str(p)] = (p.read_bytes(), p.stat().st_mtime_ns)
    return snap


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


MANIFEST_SPEC_BUNDLE_HASH = "sha256:" + "a" * 64
MANIFEST_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}


def _run_case(call_spec_bundle_hash, call_gate_versions, expected_hit):
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        gen_dir = repo_root / "gen" / "foo"
        gen_dir.mkdir(parents=True)
        manifest_path = gen_dir / ".provenance.json"

        _write_manifest(manifest_path, MANIFEST_SPEC_BUNDLE_HASH, MANIFEST_GATE_VERSIONS)

        before_content = manifest_path.read_bytes()
        before_mtime_ns = manifest_path.stat().st_mtime_ns
        before_snapshot = _snapshot(repo_root)

        time.sleep(0.01)

        result = provenance_checker.check_provenance(
            "comp-foo",
            call_spec_bundle_hash,
            call_gate_versions,
            repo_root,
        )

        hit = _field(result, "hit")
        assert hit is expected_hit

        after_content = manifest_path.read_bytes()
        after_mtime_ns = manifest_path.stat().st_mtime_ns
        after_snapshot = _snapshot(repo_root)

        assert after_content == before_content
        assert after_mtime_ns == before_mtime_ns
        assert after_snapshot == before_snapshot
        assert set(after_snapshot.keys()) == {str(manifest_path)}


def test_check_provenance_is_read_only_on_hit():
    _run_case(MANIFEST_SPEC_BUNDLE_HASH, dict(MANIFEST_GATE_VERSIONS), expected_hit=True)


def test_check_provenance_is_read_only_on_miss():
    mismatched_hash = "sha256:" + "b" * 64
    _run_case(mismatched_hash, dict(MANIFEST_GATE_VERSIONS), expected_hit=False)