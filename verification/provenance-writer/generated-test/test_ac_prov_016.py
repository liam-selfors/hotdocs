import json
import os
import tempfile
import types
from pathlib import Path

import provenance_writer


def _find_manifest_files(repo_root):
    found = []
    for dirpath, _, filenames in os.walk(repo_root):
        for name in filenames:
            if "provenance" in name and name.endswith(".json"):
                found.append(os.path.join(dirpath, name))
    return found


def test_ac_prov_016_simplenamespace_scan_results_round_trip():
    component_id = "comp-foo"
    repo_root = Path(tempfile.mkdtemp())

    license_scan_result = types.SimpleNamespace(
        component_id=component_id,
        gate_version="license_scanner@3.1.0",
        similarity_score=0.55,
        block_threshold=0.70,
        blocked=False,
        matches=[
            {
                "reference_id": "ref-123",
                "license_family": "gpl-3.0",
                "risk_tier": "high",
                "score": 0.55,
            }
        ],
        notified=True,
        notification_delivery_error=None,
        cache_hit=False,
    )

    secret_scan_result = types.SimpleNamespace(
        scope="full",
        gate_version="secret_scanner@2.0.0",
        flagged=False,
        matches=[
            {
                "rule_id": "aws-access-key-id",
                "risk_tier": "high",
                "file": "gen/foo/config.py",
                "line": 12,
            }
        ],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )

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

    inputs = provenance_writer.ProvenanceInputs(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    manifest_paths = _find_manifest_files(repo_root)
    assert manifest_paths, f"no provenance manifest file found under {repo_root}"

    expected_license_scan = vars(license_scan_result)
    expected_secret_scan = vars(secret_scan_result)

    for manifest_path in manifest_paths:
        with open(manifest_path) as f:
            manifest = json.load(f)

        written_license_scan = manifest["license_scan"]
        written_secret_scan = manifest["secret_scan"]

        for key, value in expected_license_scan.items():
            assert written_license_scan[key] == value, (
                f"license_scan.{key} mismatch in {manifest_path}: "
                f"expected {value!r}, got {written_license_scan.get(key)!r}"
            )

        for key, value in expected_secret_scan.items():
            assert written_secret_scan[key] == value, (
                f"secret_scan.{key} mismatch in {manifest_path}: "
                f"expected {value!r}, got {written_secret_scan.get(key)!r}"
            )