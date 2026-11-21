# hotdocs-criterion: sha256:cd09774c476b03ebeee9bea02d0b72ae632f88ec8283bc9b8afe34b9087a2272
import json

import provenance_writer


# SPEC_GUIDELINES.md §7's field list for the provenance manifest, as reproduced
# in provenance-writer's interface/data (the schema itself, not a redefinition).
SECTION_7_FIELDS = {
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


def _complete_inputs():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-003"],
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge",
             "result": "skipped", "rationale": None},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "skipped"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {"kind": "python", "path": ".", "definition_sha256": None,
             "adapter_sha256": "sha256:" + "b" * 64,
             "versions": {"python": "3.12.4"}, "lockfile_sha256": None},
        ],
        "overall": "pass",
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
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 2,
        "attempt_history": [
            {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
             "error_category": None, "failed_requirements": ["R-FOO-003"],
             "transcript_sha256": None},
            {"number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-003"],
             "error_category": None, "failed_requirements": [],
             "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def test_manifest_top_level_keys_exactly_match_section_7(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance("comp-foo", _complete_inputs(), repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)
        keys = set(manifest.keys())
        extra = keys - SECTION_7_FIELDS
        missing = SECTION_7_FIELDS - keys
        assert not extra, "extra keys in " + str(path) + ": " + repr(sorted(extra))
        assert not missing, "missing keys in " + str(path) + ": " + repr(sorted(missing))
        assert keys == SECTION_7_FIELDS