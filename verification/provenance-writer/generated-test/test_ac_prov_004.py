import json
from pathlib import Path

import provenance_writer


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def test_ac_prov_004(tmp_path):
    repo_root = tmp_path

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc123",
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"spec_linter.py": "# content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": "comp-foo",
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

    inputs = {
        "component_id": "comp-foo",
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    manifest_paths = list(Path(repo_root).rglob(".provenance.json"))
    assert manifest_paths, "write_provenance did not write any .provenance.json manifest"

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text())
        assert field(manifest, "provenance_hit") is True