import json
import shutil
import tempfile
from pathlib import Path

import provenance_writer


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def test_ac_prov_005():
    repo_root = Path(tempfile.mkdtemp())
    try:
        component_id = "comp-widget"

        verification_report = {
            "component_id": component_id,
            "criteria": [
                {
                    "id": "AC-WIDGET-001",
                    "covers": "R-WIDGET-001",
                    "kind": "compiled",
                    "result": "fail",
                    "failure_detail": {
                        "message": "result.foo equals 5 failed",
                        "expected": 5,
                        "actual": 3,
                    },
                },
                {
                    "id": "AC-WIDGET-002",
                    "covers": "R-WIDGET-002",
                    "kind": "llm-judge",
                    "result": "skipped",
                    "rationale": None,
                },
                {
                    "id": "AC-WIDGET-003",
                    "covers": "R-WIDGET-003",
                    "kind": "generated-test",
                    "result": "pass",
                    "test_authoring": {
                        "model": "gpt-5",
                        "seed": 0,
                        "prompt_version": "v1",
                        "cache_hit": False,
                    },
                },
            ],
            "requirement_results": {
                "R-WIDGET-001": "fail",
                "R-WIDGET-002": "fail",
                "R-WIDGET-003": "pass",
            },
            "interface_drift": False,
            "mutation_score": 0.92,
            "overall": "fail",
        }

        generation_result = {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v1",
            "cache_hit": False,
            "files": {"widget.py": "print('hello')"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
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

        inputs = {
            "component_id": component_id,
            "generation_result": generation_result,
            "verification_report": verification_report,
            "license_scan_result": license_scan_result,
            "secret_scan_result": secret_scan_result,
            "provenance_hit": False,
            "attempts": 1,
            "gate_versions": {
                "compiler": "1.0.0",
                "license_scanner": "license_scanner@3.1.0",
                "secret_scanner": "secret_scanner@2.0.0",
            },
        }

        provenance_writer.write_provenance(component_id, inputs, repo_root)

        manifest_paths = list(repo_root.rglob(".provenance.json"))
        assert manifest_paths, "write_provenance did not write any .provenance.json manifest"

        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text())
            written_report = field(manifest, "verification_report")
            assert written_report == verification_report, (
                f"{manifest_path}: verification_report in manifest does not match "
                "the full VerificationReport supplied - it must not be summarized "
                f"or truncated. Got: {written_report!r}"
            )
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)