import json

import provenance_writer


def _make_inputs():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": None,
    }
    license_scan_result = {
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
    }
    secret_scan_result = {
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
    return provenance_writer.ProvenanceInputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=2,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def _read_manifest(repo_root):
    manifest_path = repo_root / "gen" / "foo" / ".provenance.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_verification_run_id_matches_slug_attempt_formula(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()

    provenance_writer.write_provenance("comp-foo", _make_inputs(), repo_root)

    manifest = _read_manifest(repo_root)
    assert _get(manifest, "verification_run_id") == "foo-attempt-2"


def test_verification_run_id_is_deterministic_across_runs(tmp_path):
    repo_root_a = tmp_path / "repo_a"
    repo_root_a.mkdir()
    repo_root_b = tmp_path / "repo_b"
    repo_root_b.mkdir()

    inputs = _make_inputs()

    provenance_writer.write_provenance("comp-foo", inputs, repo_root_a)
    provenance_writer.write_provenance("comp-foo", inputs, repo_root_b)

    manifest_a = _read_manifest(repo_root_a)
    manifest_b = _read_manifest(repo_root_b)

    run_id_a = _get(manifest_a, "verification_run_id")
    run_id_b = _get(manifest_b, "verification_run_id")

    assert run_id_a == run_id_b == "foo-attempt-2"