import pathlib

import pytest

import provenance_writer


def _make_inputs(component_id):
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "ab" * 32,
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
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
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

    fields = dict(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        },
    )

    ProvenanceInputs = getattr(provenance_writer, "ProvenanceInputs", None)
    if ProvenanceInputs is not None:
        try:
            return ProvenanceInputs(**fields)
        except TypeError:
            pass
    return fields


def test_gen_and_verification_manifests_are_byte_identical(tmp_path):
    component_id = "comp-foo"
    slug = component_id[len("comp-"):]
    repo_root = tmp_path

    inputs = _make_inputs(component_id)

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    gen_path = pathlib.Path(repo_root) / "gen" / slug / ".provenance.json"
    verification_path = (
        pathlib.Path(repo_root) / "verification" / slug / ".provenance.json"
    )

    assert gen_path.is_file(), f"expected manifest at {gen_path}"
    assert verification_path.is_file(), f"expected manifest at {verification_path}"

    gen_bytes = gen_path.read_bytes()
    verification_bytes = verification_path.read_bytes()

    assert gen_bytes == verification_bytes, (
        "gen/<component>/.provenance.json and "
        "verification/<component>/.provenance.json MUST be byte-identical"
    )

    assert len(gen_bytes) > 0