# hotdocs-criterion: sha256:999cf3a0febfb76fc9c3dc5bf4b4bd13467048361d99eaf6dd67aa442563ae97
import json
from pathlib import Path

import pytest

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


def _minimal_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }


def _full_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": {
            "component_id": "comp-foo",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"foo.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-FOO-003"],
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
            "transcript": "secret transcript text",
            "unexpected_generation_field": "should not appear",
        },
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "assets": [
                {
                    "kind": "python",
                    "path": ".",
                    "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "b" * 64,
                    "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None,
                }
            ],
            "drivers": [],
            "overall": "pass",
        },
        "license_scan_result": {
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
        "secret_scan_result": {
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
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [
            {
                "number": 1,
                "outcome": "verification_failed",
                "retry_feedback": [],
                "error_category": None,
                "failed_requirements": ["R-FOO-003"],
                "transcript_sha256": None,
            },
            {
                "number": 2,
                "outcome": "passed",
                "retry_feedback": ["R-FOO-003"],
                "error_category": None,
                "failed_requirements": [],
                "transcript_sha256": None,
            },
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
        "spec_bundle_parts": {
            "spec": "sha256:" + "c" * 64,
            "dependency_code": "sha256:" + "d" * 64,
        },
        "extra_top_level_input": "should not appear",
    }


@pytest.mark.parametrize("make_inputs", [_minimal_inputs, _full_inputs], ids=["minimal", "full"])
def test_written_manifest_is_valid_json_with_exact_key_set(tmp_path, make_inputs):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = provenance_writer.write_provenance("comp-foo", make_inputs(), repo_root)
    assert result is None

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + str(path)
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except ValueError as exc:  # pragma: no cover - failure path
            pytest.fail("manifest at " + str(path) + " is not valid JSON: " + repr(exc))
        assert isinstance(data, dict), "manifest top level must be a JSON object"
        keys = set(data.keys())
        missing = EXPECTED_KEYS - keys
        extra = keys - EXPECTED_KEYS
        assert not missing, "missing keys in " + str(path) + ": " + repr(sorted(missing))
        assert not extra, "extra keys in " + str(path) + ": " + repr(sorted(extra))
        assert keys == EXPECTED_KEYS