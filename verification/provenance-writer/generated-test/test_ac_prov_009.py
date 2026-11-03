import json

import provenance_writer


def test_provenance_hit_writes_report_and_scans_verbatim_without_lookup(tmp_path):
    repo_root = tmp_path
    component_id = "comp-prov-hit-sample"
    slug = "prov-hit-sample"

    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": True,
        "files": {"sample.py": "print('hello')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    verification_report = {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-PROV-HIT-001",
                "covers": "R-PROV-HIT-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PROV-HIT-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.12,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
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
        "cache_hit": True,
    }

    gate_versions = {
        "compiler": "1.0.0",
        "license_scanner": "license_scanner@4.0.3",
        "secret_scanner": "secret_scanner@3.0.0+detect-secrets.1.5.0",
    }

    inputs = provenance_writer.ProvenanceInputs(
        component_id=component_id,
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=True,
        attempts=1,
        gate_versions=gate_versions,
    )

    # No gen/cache-manager, gen/verifier-orchestrator, gen/license-scanner,
    # gen/secret-scanner, or gen/provenance-checker exists anywhere under
    # repo_root: if write_provenance tried to look any of these three
    # fields up itself, the dynamic dependency loader would find nothing
    # and raise, rather than silently succeeding below.
    provenance_writer.write_provenance(component_id, inputs, repo_root)

    gen_manifest_path = repo_root / "gen" / slug / ".provenance.json"
    verif_manifest_path = repo_root / "verification" / slug / ".provenance.json"

    assert gen_manifest_path.is_file()
    assert verif_manifest_path.is_file()

    gen_manifest = json.loads(gen_manifest_path.read_text())
    verif_manifest = json.loads(verif_manifest_path.read_text())

    for manifest in (gen_manifest, verif_manifest):
        assert manifest["verification_report"] == verification_report
        assert manifest["license_scan"] == license_scan_result
        assert manifest["secret_scan"] == secret_scan_result
        assert manifest["provenance_hit"] is True