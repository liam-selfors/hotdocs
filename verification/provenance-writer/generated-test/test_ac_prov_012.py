import json
import os
import tempfile
from pathlib import Path

import provenance_writer


def _field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _find_manifests(repo_root):
    manifests = []
    for dirpath, _, filenames in os.walk(repo_root):
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    continue
            if isinstance(data, dict) and "pipeline_version" in data:
                manifests.append(data)
    return manifests


def _make_inputs(component_id, generation_result, verification_report,
                  license_scan_result, secret_scan_result, provenance_hit,
                  attempts, gate_versions):
    return {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": provenance_hit,
        "attempts": attempts,
        "gate_versions": gate_versions,
    }


def test_pipeline_version_identical_and_equals_constant_across_calls():
    generation_result_a = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:aaa111",
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('a')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report_a = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    license_scan_a = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_a = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    inputs_a = _make_inputs(
        "comp-foo", generation_result_a, verification_report_a,
        license_scan_a, secret_scan_a, False, 1,
        {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )

    generation_result_b = {
        "component_id": "comp-bar",
        "spec_bundle_hash": "sha256:bbb222",
        "model": "claude-sonnet-5",
        "prompt_version": "v2",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": ["R-BAR-002"],
    }
    license_scan_b = {
        "component_id": "comp-bar",
        "gate_version": "license_scanner@3.2.0",
        "similarity_score": 0.9,
        "block_threshold": 0.70,
        "blocked": True,
        "matches": [
            {"reference_id": "ref-9", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.9}
        ],
        "notified": True,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan_b = {
        "scope": "full",
        "gate_version": "secret_scanner@2.1.0",
        "flagged": True,
        "matches": [
            {"rule_id": "aws-access-key-id", "risk_tier": "high", "file": "gen/bar/x.py", "line": 3}
        ],
        "notified": True,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    inputs_b = _make_inputs(
        "comp-bar", generation_result_b, None,
        license_scan_b, secret_scan_b, True, 5,
        {"compiler": "1.1.0", "license_scanner": "k-gram@2.0.0"},
    )

    with tempfile.TemporaryDirectory() as repo_root_a_str, \
            tempfile.TemporaryDirectory() as repo_root_b_str:
        repo_root_a = Path(repo_root_a_str)
        repo_root_b = Path(repo_root_b_str)

        provenance_writer.write_provenance("comp-foo", inputs_a, repo_root_a)
        provenance_writer.write_provenance("comp-bar", inputs_b, repo_root_b)

        manifests_a = _find_manifests(repo_root_a)
        manifests_b = _find_manifests(repo_root_b)

        assert manifests_a, "expected at least one written manifest for comp-foo"
        assert manifests_b, "expected at least one written manifest for comp-bar"

        pipeline_versions_a = {_field(m, "pipeline_version") for m in manifests_a}
        pipeline_versions_b = {_field(m, "pipeline_version") for m in manifests_b}

        assert len(pipeline_versions_a) == 1, (
            "all manifest locations for a single write_provenance call must agree "
            "on pipeline_version"
        )
        assert len(pipeline_versions_b) == 1, (
            "all manifest locations for a single write_provenance call must agree "
            "on pipeline_version"
        )

        pipeline_version_a = pipeline_versions_a.pop()
        pipeline_version_b = pipeline_versions_b.pop()

        assert pipeline_version_a == pipeline_version_b
        assert pipeline_version_a == provenance_writer.PIPELINE_VERSION