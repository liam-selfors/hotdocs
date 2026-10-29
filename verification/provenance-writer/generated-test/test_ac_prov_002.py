import json
import tempfile
from pathlib import Path

import provenance_writer


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _contains_sample_index(value):
    if isinstance(value, dict):
        if "sample_index" in value:
            return True
        return any(_contains_sample_index(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_sample_index(v) for v in value)
    return False


def test_ac_prov_002():
    repo_root = Path(tempfile.mkdtemp())

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
    }

    verification_report = {
        "component_id": "comp-foo",
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
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    manifest_paths = list(repo_root.rglob(".provenance.json"))
    assert manifest_paths, "expected at least one provenance manifest to be written"

    for path in manifest_paths:
        manifest = json.loads(path.read_text())

        assert field(manifest, "model_pin") == "claude-sonnet-5"
        assert field(manifest, "prompt_version") == "v1"
        assert field(manifest, "retry_feedback") == ["R-FOO-002"]
        assert not _contains_sample_index(manifest)