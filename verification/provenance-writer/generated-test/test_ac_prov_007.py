import json
import os
import tempfile
from pathlib import Path

import provenance_writer


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _find_manifest_files(repo_root):
    found = []
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = Path(dirpath) / filename
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(data, dict) and "license_scan" in data and "secret_scan" in data:
                found.append((path, data))
    return found


def test_ac_prov_007_clean_scans_both_present_in_manifest():
    repo_root = Path(tempfile.mkdtemp(prefix="hotdocs-prov-007-"))
    component_id = "comp-widget"

    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.05,
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

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": None,
    }

    inputs = {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": None,
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

    result = provenance_writer.write_provenance(component_id, inputs, repo_root)
    assert result is None

    manifests = _find_manifest_files(repo_root)
    assert manifests, "write_provenance did not write any manifest file containing both scan fields"

    for path, manifest in manifests:
        license_scan = field(manifest, "license_scan")
        secret_scan = field(manifest, "secret_scan")

        assert license_scan is not None, f"license_scan missing/null in manifest at {path}"
        assert secret_scan is not None, f"secret_scan missing/null in manifest at {path}"

        assert field(license_scan, "blocked") is False
        assert field(license_scan, "matches") == []
        assert field(secret_scan, "flagged") is False
        assert field(secret_scan, "matches") == []