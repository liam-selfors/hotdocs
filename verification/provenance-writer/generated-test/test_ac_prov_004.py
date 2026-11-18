# hotdocs-criterion: sha256:01f23876761892af48a183e72e48419b2cbe11978938fe9501480af25aaea456
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        # Deliberately false: provenance_hit must come from ProvenanceInputs,
        # never inferred from any gate's own cache_hit.
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
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
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }


def _license_scan_result():
    return {
        "component_id": COMPONENT_ID,
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


def _secret_scan_result():
    return {
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


def _inputs_fields():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": True,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _build_inputs():
    fields = _inputs_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None:
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def test_provenance_hit_true_is_written_to_manifest(tmp_path):
    repo_root = Path(tmp_path)
    inputs = _build_inputs()

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for manifest_path in manifest_paths:
        assert manifest_path.is_file(), "manifest missing at " + str(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "provenance_hit" in manifest
        assert field(manifest, "provenance_hit") is True