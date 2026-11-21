# hotdocs-criterion: sha256:d536e3dcb5ec925fe523542c427a2c01a305622d309a34764aad46f67b15ea7d
import json
from pathlib import Path

import pytest

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _rich_inputs(component_id):
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {"widget.py": "x = 1\n"},
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
                {"id": "AC-WIDGET-003", "covers": "R-WIDGET-003",
                 "kind": "generated-test", "result": "pass",
                 "test_authoring": {"model": "gpt-5", "seed": 0,
                                    "prompt_version": "v1", "cache_hit": False}},
            ],
            "requirement_results": {"R-WIDGET-001": "pass", "R-WIDGET-003": "pass"},
            "interface_drift": False,
            "mutation_score": 0.92,
            "mutation_error": None,
            "assets": [
                {"kind": "python", "path": ".", "definition_sha256": None,
                 "adapter_sha256": "sha256:" + "b" * 64,
                 "versions": {"python": "3.12.4"}, "lockfile_sha256": None},
                {"kind": "javascript", "path": "static/app.js",
                 "definition_sha256": "sha256:" + "c" * 64,
                 "adapter_sha256": "sha256:" + "d" * 64,
                 "versions": {"node": "24.1.0"}, "lockfile_sha256": None},
            ],
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
             "failed_requirements": ["R-WIDGET-003"], "transcript_sha256": None},
            {"number": 2, "outcome": "passed",
             "retry_feedback": ["R-WIDGET-003"], "error_category": None,
             "failed_requirements": [], "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0",
                          "odd": {"b", "a"}, "where": Path("p")},
    }


@pytest.mark.parametrize("builder", [_minimal_inputs, _rich_inputs],
                         ids=["minimal", "rich"])
def test_both_manifests_are_byte_identical(tmp_path, builder):
    component_id = "comp-widget"
    slug = "widget"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = provenance_writer.write_provenance(component_id, builder(component_id), repo_root)
    assert result is None

    gen_manifest = repo_root / "gen" / slug / ".provenance.json"
    ver_manifest = repo_root / "verification" / slug / ".provenance.json"

    assert gen_manifest.is_file(), "gen manifest not written"
    assert ver_manifest.is_file(), "verification manifest not written"

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()

    assert len(gen_bytes) > 0
    assert gen_bytes == ver_bytes

    # Both are the same valid JSON document.
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(parsed, dict)
    assert parsed == json.loads(ver_bytes.decode("utf-8"))


def test_repeated_write_keeps_copies_identical(tmp_path):
    component_id = "comp-widget"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(component_id, _minimal_inputs(component_id), repo_root)
    provenance_writer.write_provenance(component_id, _rich_inputs(component_id), repo_root)

    gen_bytes = (repo_root / "gen" / "widget" / ".provenance.json").read_bytes()
    ver_bytes = (repo_root / "verification" / "widget" / ".provenance.json").read_bytes()
    assert gen_bytes == ver_bytes