# hotdocs-criterion: sha256:25c4d1886e7829fa46c6a41a66fbb938859cd3110210c1dd5c991c83838dda12
import json
from pathlib import Path

import pytest

import provenance_writer


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
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"widget.py": "def f():\n    return 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-WIDGET-003"],
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001",
                 "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-WIDGET-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                        "adapter_sha256": "sha256:" + "b" * 64,
                        "versions": {"python": "3.12.4"},
                        "lockfile_sha256": None}],
            "overall": "pass",
        },
        "license_scan_result": {
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
            {"number": 1, "outcome": "verification_failed",
             "retry_feedback": [], "error_category": None,
             "failed_requirements": ["R-WIDGET-003"],
             "transcript_sha256": None},
            {"number": 2, "outcome": "passed",
             "retry_feedback": ["R-WIDGET-003"], "error_category": None,
             "failed_requirements": [], "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0",
                          "license_scanner": "k-gram@1.0.0"},
    }


@pytest.mark.parametrize("builder", [_minimal_inputs, _full_inputs],
                         ids=["minimal", "full"])
def test_both_manifests_are_byte_identical(tmp_path, builder):
    component_id = "comp-widget"
    repo_root = Path(tmp_path)

    provenance_writer.write_provenance(component_id, builder(component_id), repo_root)

    gen_path = repo_root / "gen" / "widget" / ".provenance.json"
    ver_path = repo_root / "verification" / "widget" / ".provenance.json"

    assert gen_path.is_file(), "gen manifest missing"
    assert ver_path.is_file(), "verification manifest missing"

    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()

    assert len(gen_bytes) > 0
    assert gen_bytes == ver_bytes

    # Both are the same, valid JSON object.
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(parsed, dict)
    assert parsed == json.loads(ver_bytes.decode("utf-8"))


def test_repeated_write_keeps_copies_identical(tmp_path):
    component_id = "comp-widget"
    repo_root = Path(tmp_path)

    provenance_writer.write_provenance(component_id, _minimal_inputs(component_id), repo_root)
    provenance_writer.write_provenance(component_id, _full_inputs(component_id), repo_root)

    gen_bytes = (repo_root / "gen" / "widget" / ".provenance.json").read_bytes()
    ver_bytes = (repo_root / "verification" / "widget" / ".provenance.json").read_bytes()

    assert gen_bytes == ver_bytes