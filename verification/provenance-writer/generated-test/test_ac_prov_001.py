import json
import tempfile
from pathlib import Path

import provenance_writer


def test_ac_prov_001():
    repo_root = Path(tempfile.mkdtemp())
    component_id = "comp-foo"

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    verification_report = {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.1,
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

    gate_versions = {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"}

    inputs = provenance_writer.ProvenanceInputs(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=2,
        gate_versions=gate_versions,
    )

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    manifest_paths = sorted(repo_root.rglob(".provenance.json"))
    assert manifest_paths, "write_provenance did not write any .provenance.json manifest"

    expected_keys = {
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

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text())
        assert set(manifest.keys()) == expected_keys