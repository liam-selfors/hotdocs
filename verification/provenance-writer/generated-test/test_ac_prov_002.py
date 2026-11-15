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
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "def run_thing(x):\n    return x\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
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
            },
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "pass",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
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


def _inputs():
    data = {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if isinstance(cls, type):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def _find_key(obj, key, path="$"):
    """Return list of JSON paths at which `key` appears as a mapping key."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}"
            if k == key:
                found.append(here)
            found.extend(_find_key(v, key, here))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_find_key(v, key, f"{path}[{i}]"))
    return found


def test_ac_prov_002_generation_fields_copied_and_no_sample_index(tmp_path):
    repo_root = Path(tmp_path)

    provenance_writer.write_provenance(COMPONENT_ID, _inputs(), repo_root)

    manifest_paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]

    for manifest_path in manifest_paths:
        assert manifest_path.is_file(), f"manifest not written at {manifest_path}"
        raw = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(raw)
        assert isinstance(manifest, dict)

        assert field(manifest, "model_pin") == "claude-sonnet-5", manifest_path
        assert field(manifest, "prompt_version") == "v1", manifest_path
        assert field(manifest, "retry_feedback") == ["R-FOO-002"], manifest_path

        occurrences = _find_key(manifest, "sample_index")
        assert occurrences == [], (
            f"sample_index present in {manifest_path} at {occurrences}"
        )
        assert "sample_index" not in raw, (
            f"sample_index text present in {manifest_path}"
        )