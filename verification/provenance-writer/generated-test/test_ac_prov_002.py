import json

import provenance_writer


def _contains_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key(v, key) for v in obj)
    return False


def test_ac_prov_002(tmp_path):
    component_id = "comp-foo"
    slug = "foo"
    repo_root = tmp_path

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": None,
        "refused": "sealed-component",
        "retry_feedback": ["R-FOO-002"],
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

    inputs = provenance_writer.ProvenanceInputs(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        },
    )

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    gen_manifest_path = repo_root / "gen" / slug / ".provenance.json"
    verification_manifest_path = repo_root / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verification_manifest_path.is_file()

    for manifest_path in (gen_manifest_path, verification_manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["model_pin"] == "claude-sonnet-5"
        assert manifest["prompt_version"] == "v1"
        assert manifest["retry_feedback"] == ["R-FOO-002"]
        assert not _contains_key(manifest, "sample_index")