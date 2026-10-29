import json

import provenance_writer
from provenance_writer import ProvenanceInputs, write_provenance


def _build_inputs():
    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"spec_linter.py": "print('hello')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
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
        "mutation_score": 0.92,
        "overall": "pass",
    }
    license_scan_result = {
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
    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    return ProvenanceInputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )


def test_gen_and_verification_copies_are_byte_identical(tmp_path):
    repo_root = tmp_path
    inputs = _build_inputs()

    write_provenance("comp-foo", inputs, repo_root)

    gen_path = repo_root / "gen" / "foo" / ".provenance.json"
    verification_path = repo_root / "verification" / "foo" / ".provenance.json"

    assert gen_path.is_file()
    assert verification_path.is_file()

    gen_bytes = gen_path.read_bytes()
    verification_bytes = verification_path.read_bytes()

    assert gen_bytes == verification_bytes

    # Confirm the two copies are a real manifest, not two identical empty files.
    manifest = json.loads(gen_bytes)
    assert manifest