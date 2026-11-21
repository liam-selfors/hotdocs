# hotdocs-criterion: sha256:40e4bcd1fbed0cd631c3ef5e3169b14d270def6eaceceac7bc743231646a1f2f
import json
from pathlib import Path

import pytest

import provenance_writer


# SPEC_GUIDELINES.md §7's top-level field list for the provenance manifest,
# as reproduced in the component's interface/data/ provenance manifest document.
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


def _assets():
    return [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:" + "a" * 64,
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ]


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": _assets(),
        "overall": "pass",
    }


def _generation_result(files):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-003"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
        # Extra field that must never be written into the manifest.
        "transcript": "a transcript that must not appear",
    }


def _license_scan_result():
    return {
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


def _secret_scan_result():
    return {
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


def _complete_inputs():
    return {
        "component_id": "comp-foo",
        "generation_result": _generation_result({"foo.py": "def f():\n    return 1\n"}),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
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
        # Extra input key that must be ignored, never written.
        "unexpected_extra_input": "ignore me",
    }


def _no_candidate_inputs():
    inputs = _complete_inputs()
    inputs["generation_result"] = _generation_result({})
    inputs["generation_result"]["model_call_error"] = {
        "category": "network",
        "message": "unreachable",
    }
    inputs["verification_report"] = None
    inputs["attempts"] = 1
    inputs["attempt_history"] = [
        {
            "number": 1,
            "outcome": "model_call_error",
            "retry_feedback": [],
            "error_category": "network",
            "failed_requirements": [],
            "transcript_sha256": None,
        }
    ]
    return inputs


def _read_manifests(repo_root):
    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    manifests = []
    for path in paths:
        assert path.is_file(), "manifest not written at " + str(path)
        with open(path, "r", encoding="utf-8") as fh:
            manifests.append(json.load(fh))
    return manifests


@pytest.mark.parametrize(
    "build_inputs",
    [_complete_inputs, _no_candidate_inputs],
    ids=["verified-candidate", "no-candidate"],
)
def test_manifest_top_level_keys_exactly_match_spec_guidelines_section_7(tmp_path, build_inputs):
    repo_root = Path(tmp_path)
    inputs = build_inputs()

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        assert isinstance(manifest, dict)
        keys = set(manifest.keys())
        missing = EXPECTED_KEYS - keys
        extra = keys - EXPECTED_KEYS
        assert not missing, "manifest is missing §7 fields: " + repr(sorted(missing))
        assert not extra, "manifest has fields §7 does not declare: " + repr(sorted(extra))
        assert len(manifest) == len(EXPECTED_KEYS)