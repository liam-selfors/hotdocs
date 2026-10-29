import json
import tempfile
from pathlib import Path

import provenance_writer


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def test_ac_prov_003_gate_versions_exact_and_unmodified():
    repo_root = Path(tempfile.mkdtemp())

    generation_result = {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": "connection reset by peer",
        "refused": None,
        "retry_feedback": None,
    }

    license_scan_result = {
        "component_id": "comp-widget",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.10,
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

    reported_gate_versions = {
        "cache_manager": "cache_manager@4.2.0",
        "compiler": "criterion_compiler@1.4.0",
        "license_scanner": "license_scanner@3.1.0",
    }

    inputs = {
        "component_id": "comp-widget",
        "generation_result": generation_result,
        "verification_report": None,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": dict(reported_gate_versions),
    }

    provenance_writer.write_provenance("comp-widget", inputs, repo_root)

    manifest_paths = sorted(repo_root.rglob(".provenance.json"))
    assert len(manifest_paths) >= 2

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text())
        assert field(manifest, "gate_versions") == reported_gate_versions