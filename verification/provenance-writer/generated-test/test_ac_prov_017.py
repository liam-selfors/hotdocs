import dataclasses
import json
from pathlib import Path

import pytest

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _build_inputs():
    component_id = "comp-foo"

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + ("0123456789abcdef" * 4),
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hello')\n"},
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
        component_id=component_id,
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def test_provenance_inputs_is_a_real_dataclass():
    assert hasattr(provenance_writer, "ProvenanceInputs")
    cls = provenance_writer.ProvenanceInputs
    assert dataclasses.is_dataclass(cls)

    inputs = _build_inputs()
    assert dataclasses.is_dataclass(inputs)

    field_names = {f.name for f in dataclasses.fields(cls)}
    for required in (
        "component_id",
        "generation_result",
        "verification_report",
        "license_scan_result",
        "secret_scan_result",
        "provenance_hit",
        "attempts",
        "gate_versions",
    ):
        assert required in field_names

    assert _get(inputs, "component_id") == "comp-foo"
    assert _get(inputs, "provenance_hit") is False
    assert _get(inputs, "attempts") == 1


def test_write_provenance_writes_manifest_without_raising(tmp_path):
    inputs = _build_inputs()
    repo_root = tmp_path

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    gen_manifest = repo_root / "gen" / "foo" / ".provenance.json"
    verification_manifest = repo_root / "verification" / "foo" / ".provenance.json"

    assert gen_manifest.exists()
    assert verification_manifest.exists()

    gen_payload = json.loads(gen_manifest.read_text())
    verification_payload = json.loads(verification_manifest.read_text())

    assert isinstance(gen_payload, dict)
    assert isinstance(verification_payload, dict)