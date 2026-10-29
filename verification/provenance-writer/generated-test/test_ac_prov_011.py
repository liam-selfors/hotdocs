import json
import os
import pathlib
import tempfile

import provenance_writer


EXPECTED_KEYS = {
    "spec_bundle_hash",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
}


def _build_inputs(component_id):
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"sample.py": "print('hello')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-SAMPLE-001",
                "covers": "R-SAMPLE-001",
                "kind": "compiled",
                "result": "pass",
            },
        ],
        "requirement_results": {"R-SAMPLE-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
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
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _find_provenance_manifests(repo_root):
    # Glossary: a provenance manifest is always a `.provenance.json` file.
    found = []
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for filename in filenames:
            if filename.endswith(".provenance.json"):
                found.append(os.path.join(dirpath, filename))
    return found


def test_written_manifest_is_valid_json_with_exact_key_set():
    component_id = "comp-sample"
    inputs = _build_inputs(component_id)
    repo_root = pathlib.Path(tempfile.mkdtemp())

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    manifest_paths = _find_provenance_manifests(repo_root)
    assert manifest_paths, "expected at least one .provenance.json file to be written"

    for manifest_path in manifest_paths:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        assert set(manifest.keys()) == EXPECTED_KEYS