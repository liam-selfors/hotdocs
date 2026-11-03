import json
import tempfile
from pathlib import Path

import pytest

import provenance_writer


EXPECTED_SCHEMA_KEYS = {
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


def _build_inputs():
    generation_result = {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"widget_maker.py": "# generated code\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    verification_report = {
        "component_id": "comp-widget-maker",
        "criteria": [
            {
                "id": "AC-WIDGET-MAKER-001",
                "covers": "R-WIDGET-MAKER-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-WIDGET-MAKER-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": "comp-widget-maker",
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
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
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    return provenance_writer.ProvenanceInputs(
        component_id="comp-widget-maker",
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def test_written_provenance_file_is_valid_json_with_exact_schema_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        inputs = _build_inputs()

        provenance_writer.write_provenance("comp-widget-maker", inputs, repo_root)

        gen_path = repo_root / "gen" / "widget-maker" / ".provenance.json"
        verification_path = repo_root / "verification" / "widget-maker" / ".provenance.json"

        for manifest_path in (gen_path, verification_path):
            assert manifest_path.is_file(), f"expected manifest at {manifest_path}"

            with open(manifest_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            parsed = json.loads(raw_text)

            assert isinstance(parsed, dict)
            assert set(parsed.keys()) == EXPECTED_SCHEMA_KEYS