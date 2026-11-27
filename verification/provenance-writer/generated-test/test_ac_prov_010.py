# hotdocs-criterion: sha256:eae63e4424737271a7745a9c2734c300a6b6e0e7b7b1f9fff8c345d7a6d72713
"""AC-PROV-010: both provenance manifest copies are byte-identical (R-PROV-010)."""

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
                {"id": "AC-WIDGET-002", "covers": "R-WIDGET-002",
                 "kind": "generated-test", "result": "fail",
                 "failure_origin": "implementation",
                 "failure_detail": {"message": "x", "expected": 5, "actual": 3}},
            ],
            "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-002": "fail"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                        "adapter_sha256": "sha256:" + "b" * 64,
                        "versions": {"python": "3.12.4"},
                        "lockfile_sha256": None}],
            "drivers": [],
            "overall": "fail",
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
            {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
             "error_category": None, "failed_requirements": ["R-WIDGET-003"],
             "transcript_sha256": None},
            {"number": 2, "outcome": "verification_failed",
             "retry_feedback": ["R-WIDGET-003"], "error_category": None,
             "failed_requirements": ["R-WIDGET-002"], "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0",
                          "license_scanner": "k-gram@1.0.0",
                          "unicode": "\u00e9\u2603"},
        "spec_bundle_parts": {"spec": "sha256:" + "c" * 64,
                              "dependency_code": "sha256:" + "d" * 64},
    }


@pytest.mark.parametrize("builder", [_minimal_inputs, _full_inputs],
                         ids=["minimal", "full"])
def test_ac_prov_010_both_manifest_copies_byte_identical(tmp_path, builder):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-widget"
    slug = "widget"

    result = provenance_writer.write_provenance(
        component_id, builder(component_id), repo_root
    )
    assert result is None

    gen_path = repo_root / "gen" / slug / ".provenance.json"
    ver_path = repo_root / "verification" / slug / ".provenance.json"

    assert gen_path.is_file(), "missing " + str(gen_path)
    assert ver_path.is_file(), "missing " + str(ver_path)

    gen_bytes = gen_path.read_bytes()
    ver_bytes = ver_path.read_bytes()

    assert len(gen_bytes) > 0
    # Sanity: the manifest is real JSON (so we are comparing actual manifests).
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(parsed, dict)

    assert gen_bytes == ver_bytes


def test_ac_prov_010_identical_after_rewrite(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-widget"

    provenance_writer.write_provenance(
        component_id, _minimal_inputs(component_id), repo_root
    )
    provenance_writer.write_provenance(
        component_id, _full_inputs(component_id), repo_root
    )

    gen_bytes = (repo_root / "gen" / "widget" / ".provenance.json").read_bytes()
    ver_bytes = (repo_root / "verification" / "widget" / ".provenance.json").read_bytes()

    assert gen_bytes == ver_bytes
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert parsed["attempts"] == 2