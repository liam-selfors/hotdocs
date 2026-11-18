# hotdocs-criterion: sha256:34f5ccd8cd3a28d3525ab47861f207b50894481efea50d4a1d21c0dcc51b6b55
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


REPORTED_GATE_VERSIONS = {
    "cache_manager": "cache_manager@1.7.3",
    "criterion_compiler": "criterion_compiler@3.1.4+c0ffee12ab34",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
}


def _build_inputs(component_id):
    generation_result = {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
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
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    fields = {
        "component_id": component_id,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": license_scan_result,
        "secret_scan_result": secret_scan_result,
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": dict(REPORTED_GATE_VERSIONS),
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and isinstance(cls, type):
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def test_gate_versions_are_exactly_the_reported_values(tmp_path):
    repo_root = Path(tmp_path)
    component_id = "comp-foo"
    inputs = _build_inputs(component_id)

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    manifest_paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for manifest_path in manifest_paths:
        assert manifest_path.is_file(), "missing manifest: " + str(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        gate_versions = field(manifest, "gate_versions")
        assert isinstance(gate_versions, dict)
        # Exactly the three reported values, unmodified, nothing invented or added.
        assert gate_versions == REPORTED_GATE_VERSIONS
        assert sorted(gate_versions.values()) == sorted(REPORTED_GATE_VERSIONS.values())
        assert len(gate_versions) == 3