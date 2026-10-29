import json

import provenance_writer


def test_provenance_hit_writes_three_fields_verbatim_without_lookup(tmp_path):
    repo_root = tmp_path

    # Sanity check: no dependency scaffolding exists under repo_root at all.
    # If this component performed its own lookup via any dependency's
    # dynamic loader (gen/<dep>/<dep_module>.py), there is nothing here for
    # it to find -- so a successful write below is proof no lookup happened.
    assert list(repo_root.iterdir()) == []

    generation_result = {
        "component_id": "comp-target-widget",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": True,
        "files": {"widget.py": "x = 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }

    verification_report = {
        "component_id": "comp-target-widget",
        "criteria": [
            {
                "id": "AC-WIDGET-001",
                "covers": "R-WIDGET-001",
                "kind": "compiled",
                "result": "pass",
            },
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }

    license_scan_result = {
        "component_id": "comp-target-widget",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }

    secret_scan_result = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }

    inputs = provenance_writer.ProvenanceInputs(
        component_id="comp-target-widget",
        generation_result=generation_result,
        verification_report=verification_report,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=True,
        attempts=1,
        gate_versions={"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    )

    provenance_writer.write_provenance("comp-target-widget", inputs, repo_root)

    manifests = []
    for path in repo_root.rglob("*.json"):
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict) and "provenance_hit" in data:
            manifests.append(data)

    # cli.md: "Manifest written to both required locations."
    assert len(manifests) == 2

    for manifest in manifests:
        assert manifest["provenance_hit"] is True
        # The three fields must be written verbatim -- byte-for-byte equal
        # to what the caller supplied, with no lookup or transformation
        # performed by this component itself.
        assert manifest["verification_report"] == verification_report
        assert manifest["license_scan"] == license_scan_result
        assert manifest["secret_scan"] == secret_scan_result