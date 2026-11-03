import json

import provenance_checker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}


def _write_manifest(gen_dir, spec_bundle_hash, gate_versions):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
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
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))
    return manifest


def _plant_poisoned_assembler(repo_root, log_path):
    assembler_dir = repo_root / "gen" / "spec-bundle-assembler"
    assembler_dir.mkdir(parents=True)
    source = (
        "class _FakeBundle:\n"
        "    def __init__(self, spec_bundle_hash):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "\n"
        "def assemble(component_id, repo_root=None, mode=\"cold\"):\n"
        "    with open(" + repr(str(log_path)) + ", \"a\") as f:\n"
        "        f.write(str(component_id) + \"\\n\")\n"
        "    return _FakeBundle(\"sha256:\" + (\"b\" * 64))\n"
    )
    (assembler_dir / "spec_bundle_assembler.py").write_text(source)


def test_check_provenance_uses_caller_supplied_hash_not_a_self_computed_one(tmp_path):
    repo_root = tmp_path
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)

    manifest_hash = "sha256:" + ("a" * 64)
    manifest = _write_manifest(gen_dir, manifest_hash, GATE_VERSIONS)

    log_path = tmp_path / "assembler_calls.log"
    _plant_poisoned_assembler(repo_root, log_path)

    # Caller supplies exactly the manifest's own spec_bundle_hash: if check_provenance
    # compared the caller-supplied hash against the manifest, this is a hit. If it
    # instead computed its own hash (e.g. via the planted spec-bundle-assembler,
    # which would yield a different, poisoned value), it would wrongly report a miss.
    result_hit = provenance_checker.check_provenance(
        "comp-foo", manifest_hash, GATE_VERSIONS, repo_root
    )
    assert _get(result_hit, "hit") is True
    assert _get(result_hit, "verification_report") == manifest["verification_report"]
    assert _get(result_hit, "license_scan") == manifest["license_scan"]
    assert _get(result_hit, "secret_scan") == manifest["secret_scan"]
    assert not log_path.exists(), (
        "check_provenance must never consult spec-bundle-assembler to compute its "
        "own spec_bundle_hash"
    )

    # Caller supplies a different hash than the manifest's own field, with nothing
    # else about the manifest or repo changed: this must be a miss. This rules out
    # an implementation that ignores the caller-supplied value (e.g. always hitting,
    # or substituting some internally computed hash of its own that happens to
    # satisfy a different, unrelated check).
    different_hash = "sha256:" + ("c" * 64)
    result_miss = provenance_checker.check_provenance(
        "comp-foo", different_hash, GATE_VERSIONS, repo_root
    )
    assert _get(result_miss, "hit") is False
    assert _get(result_miss, "verification_report") is None
    assert _get(result_miss, "license_scan") is None
    assert _get(result_miss, "secret_scan") is None
    assert not log_path.exists(), (
        "check_provenance must never consult spec-bundle-assembler to compute its "
        "own spec_bundle_hash"
    )