# hotdocs-criterion: sha256:bd038d04b2f0f8fbaa0affd629b1d04458296fe006622c0a1b63fc9ac8d4e19d
import json
from pathlib import Path

import pytest

import provenance_writer


EXPECTED_KEYS = {
    "spec_bundle_hash",
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
}


def _reject_constant(name):
    raise ValueError("non-standard JSON constant: " + repr(name))


def _strict_parse(text):
    # Strict JSON: NaN / Infinity / -Infinity are not valid JSON.
    return json.loads(text, parse_constant=_reject_constant)


def _manifest_paths(repo_root, slug):
    return [
        Path(repo_root) / "gen" / slug / ".provenance.json",
        Path(repo_root) / "verification" / slug / ".provenance.json",
    ]


def _minimal_inputs(component_id):
    return {
        "component_id": component_id,
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }


def _full_inputs(component_id):
    generation_result = {
        "component_id": component_id,
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
        "transcript": "should never be written",
        "unexpected_extra_field": "ignored",
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
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
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": component_id,
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
        "an_extra_input_key": "must not appear in the manifest",
    }


def _assert_manifests_valid(repo_root, slug):
    for path in _manifest_paths(repo_root, slug):
        assert path.is_file(), "manifest not written at " + str(path)
        text = path.read_text(encoding="utf-8")
        try:
            parsed = _strict_parse(text)
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            pytest.fail("manifest at " + str(path) + " is not valid JSON: " + repr(exc))
        assert isinstance(parsed, dict), "manifest top level must be a JSON object"
        keys = set(parsed.keys())
        missing = EXPECTED_KEYS - keys
        extra = keys - EXPECTED_KEYS
        assert not missing, "missing keys in " + str(path) + ": " + repr(sorted(missing))
        assert not extra, "extra keys in " + str(path) + ": " + repr(sorted(extra))
        assert keys == EXPECTED_KEYS


def test_minimal_call_manifest_is_valid_json_with_exact_schema_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo"

    result = provenance_writer.write_provenance(
        component_id, _minimal_inputs(component_id), repo_root
    )
    assert result is None

    _assert_manifests_valid(repo_root, "foo")


def test_full_call_manifest_is_valid_json_with_exact_schema_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo-bar"

    provenance_writer.write_provenance(
        component_id, _full_inputs(component_id), repo_root
    )

    _assert_manifests_valid(repo_root, "foo-bar")


def test_non_finite_and_odd_values_still_yield_valid_json_with_exact_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-odd"
    inputs = _minimal_inputs(component_id)
    inputs["license_scan_result"] = {
        "similarity_score": float("nan"),
        "block_threshold": float("inf"),
        "matches": [],
    }
    inputs["secret_scan_result"] = {
        "matches": [],
        "tags": {"b", "a"},
        "raw": b"x",
        "where": Path("p"),
    }

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    _assert_manifests_valid(repo_root, "odd")