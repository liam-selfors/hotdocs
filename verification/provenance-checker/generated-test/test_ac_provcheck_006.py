import json

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _manifest(spec_bundle_hash, gate_versions):
    return {
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
            "gate_version": "license_scanner@3.1.0",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def _snapshot(repo_root):
    snapshot = {}
    for path in sorted(repo_root.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(repo_root))
            snapshot[rel] = (path.read_bytes(), path.stat().st_mtime_ns)
    return snapshot


def test_check_provenance_is_read_only_on_hit_and_miss(tmp_path):
    repo_root = tmp_path
    matching_hash = "sha256:" + "a" * 64
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@3.1.0",
        "secret_scanner": "secret_scanner@0.0.0",
    }
    manifest_text = json.dumps(
        _manifest(matching_hash, gate_versions), indent=2, sort_keys=True
    )

    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    (gen_dir / ".provenance.json").write_text(manifest_text)

    verification_dir = repo_root / "verification" / "foo"
    verification_dir.mkdir(parents=True)
    (verification_dir / ".provenance.json").write_text(manifest_text)

    before = _snapshot(repo_root)
    assert before

    hit_result = provenance_checker.check_provenance(
        "comp-foo", matching_hash, gate_versions, repo_root
    )
    assert _get(hit_result, "hit") is True
    assert _snapshot(repo_root) == before

    mismatched_hash = "sha256:" + "b" * 64
    miss_result = provenance_checker.check_provenance(
        "comp-foo", mismatched_hash, gate_versions, repo_root
    )
    assert _get(miss_result, "hit") is False
    assert _snapshot(repo_root) == before