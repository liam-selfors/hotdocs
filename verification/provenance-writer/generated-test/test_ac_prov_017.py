import dataclasses
import json
from pathlib import Path

import provenance_writer


def test_provenance_inputs_is_dataclass_and_write_provenance_runs(tmp_path):
    assert hasattr(provenance_writer, "ProvenanceInputs")
    ProvenanceInputs = provenance_writer.ProvenanceInputs
    assert dataclasses.is_dataclass(ProvenanceInputs)

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": "simulated upstream model failure",
        "refused": None,
        "retry_feedback": None,
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

    gate_versions = {
        "compiler": "1.0.0",
        "license_scanner": "k-gram@1.0.0",
    }

    inputs = ProvenanceInputs(
        component_id="comp-foo",
        generation_result=generation_result,
        verification_report=None,
        license_scan_result=license_scan_result,
        secret_scan_result=secret_scan_result,
        provenance_hit=False,
        attempts=1,
        gate_versions=gate_versions,
    )

    assert dataclasses.is_dataclass(inputs)

    repo_root = Path(tmp_path)

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    written_manifests = list(repo_root.rglob("*.provenance.json"))
    assert len(written_manifests) >= 1

    def field(obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    with open(written_manifests[0], "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert field(manifest, "spec_bundle_hash") is not None