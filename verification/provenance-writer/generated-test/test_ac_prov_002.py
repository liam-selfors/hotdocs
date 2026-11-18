# hotdocs-criterion: sha256:078ca189e4131c4085e629bb15764e1d71d64e9dbb974a8c8860b1a6137227e7
import dataclasses
import json
from pathlib import Path

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
        "files": {"foo.py": "def foo():\n    return 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": ["R-FOO-002"],
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
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


def _inputs_dict():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _build_inputs():
    data = _inputs_dict()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def _keys_anywhere(value):
    found = set()
    if isinstance(value, dict):
        for k, v in value.items():
            found.add(k)
            found |= _keys_anywhere(v)
    elif isinstance(value, list):
        for item in value:
            found |= _keys_anywhere(item)
    return found


def test_ac_prov_002_generation_fields_copied_and_no_sample_index(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    provenance_writer.write_provenance(COMPONENT_ID, _build_inputs(), repo_root)

    paths = [
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        text = path.read_text(encoding="utf-8")
        manifest = json.loads(text)
        assert isinstance(manifest, dict)

        assert field(manifest, "model_pin") == "claude-sonnet-5"
        assert field(manifest, "prompt_version") == "v1"
        assert field(manifest, "retry_feedback") == ["R-FOO-002"]

        assert "sample_index" not in _keys_anywhere(manifest)
        assert "sample_index" not in text