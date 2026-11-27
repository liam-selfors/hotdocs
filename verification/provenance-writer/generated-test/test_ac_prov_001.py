# hotdocs-criterion: sha256:cc9f9c2ec237e0a31aa8ea15c3b4128c63e183bf10b38fb95e6ba0bd9f0298f9
"""AC-PROV-001: the written manifest's top-level keys exactly match
interface/data/provenancemanifest.md's keys (R-PROV-001, D377)."""

import json
from pathlib import Path

import provenance_writer


EXPECTED_KEYS = {
    "spec_bundle_hash",
    "spec_bundle_parts",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "generation",
    "attempts",
    "attempt_history",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
    "assets",
    "drivers",
}

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def _complete_inputs(component_id):
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": SHA_A,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        # A transcript may arrive but is never written.
        "transcript": "some transcript text",
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": SHA_B,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "verification_failed",
                "retry_feedback": [],
                "error_category": None,
                "failed_requirements": ["R-FOO-002"],
                "transcript_sha256": None,
            },
            {
                "number": 2,
                "outcome": "passed",
                "retry_feedback": ["R-FOO-002"],
                "error_category": None,
                "failed_requirements": [],
                "transcript_sha256": None,
            },
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
        "spec_bundle_parts": {"spec": SHA_A, "dependency_code": SHA_C},
        # An extra key that must be ignored, never written.
        "unexpected_extra_input": "must not appear",
    }


def test_ac_prov_001_manifest_top_level_keys_exactly_match(tmp_path):
    repo_root = Path(tmp_path)
    component_id = "comp-foo"
    inputs = _complete_inputs(component_id)

    result = provenance_writer.write_provenance(component_id, inputs, repo_root)
    assert result is None

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + repr(str(path))
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)
        actual = set(manifest.keys())
        missing = EXPECTED_KEYS - actual
        extra = actual - EXPECTED_KEYS
        assert not missing, "missing keys in " + repr(str(path)) + ": " + repr(sorted(missing))
        assert not extra, "extra keys in " + repr(str(path)) + ": " + repr(sorted(extra))
        assert actual == EXPECTED_KEYS