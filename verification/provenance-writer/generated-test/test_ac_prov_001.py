"""AC-PROV-001: the written manifest's top-level keys exactly match
SPEC_GUIDELINES.md §7's field list, with no extra keys and none missing."""

import dataclasses
import json
from pathlib import Path

import provenance_writer


# SPEC_GUIDELINES.md §7's provenance manifest field list, as reproduced in
# provenance-writer's interface/data (provenance manifest).
EXPECTED_KEYS = {
    "spec_bundle_hash",
    "model_pin",
    "prompt_version",
    "retry_feedback",
    "pipeline_version",
    "gate_versions",
    "provenance_hit",
    "generated_at",
    "verification_run_id",
    "verification_report",
    "license_scan",
    "secret_scan",
}

COMPONENT_ID = "comp-widget"
SLUG = "widget"


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"widget.py": "def make_widget(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-WIDGET-001",
                "covers": "R-WIDGET-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
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


def _inputs_data():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _make_inputs():
    data = _inputs_data()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def test_ac_prov_001_manifest_top_level_keys_exactly_match_schema(tmp_path):
    repo_root = Path(tmp_path)
    (repo_root / "gen" / SLUG).mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)

    provenance_writer.write_provenance(COMPONENT_ID, _make_inputs(), repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in manifest_paths:
        assert path.is_file(), f"manifest not written at {path}"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict), f"manifest at {path} is not a JSON object"
        keys = set(manifest.keys())
        extra = keys - EXPECTED_KEYS
        missing = EXPECTED_KEYS - keys
        assert not extra, f"extra keys in {path}: {sorted(extra)}"
        assert not missing, f"missing keys in {path}: {sorted(missing)}"
        assert keys == EXPECTED_KEYS