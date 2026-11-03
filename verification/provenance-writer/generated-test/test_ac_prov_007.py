import json

import provenance_writer


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _make_inputs(**fields):
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        return cls(**fields)
    return dict(fields)


def test_clean_license_and_secret_scans_always_populated(tmp_path):
    component_id = "comp-fixture-clean-scans"
    slug = component_id[len("comp-"):]
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
        "retry_feedback": None,
    }

    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
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
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }

    inputs = _make_inputs(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions={
            "license_scanner": "license_scanner@4.0.3",
            "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        },
    )

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    gen_manifest_path = repo_root / "gen" / slug / ".provenance.json"
    verification_manifest_path = repo_root / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verification_manifest_path.is_file()

    for manifest_path in (gen_manifest_path, verification_manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)

        license_scan = _get(manifest, "license_scan")
        secret_scan = _get(manifest, "secret_scan")

        assert license_scan is not None
        assert secret_scan is not None

        assert _get(license_scan, "evaluated") is True
        assert _get(license_scan, "blocked") is False
        assert _get(license_scan, "matches") == []

        assert _get(secret_scan, "flagged") is False
        assert _get(secret_scan, "matches") == []