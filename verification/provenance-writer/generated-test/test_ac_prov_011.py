# hotdocs-criterion: sha256:71db4f86dc7012a26fb306fe914025d18d4400d76832e27b482d36d477f633a8
import json
from pathlib import Path

import pytest

import provenance_writer


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result(component_id, with_files):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "x = 1\n"} if with_files else {},
        "model_call_error": None if with_files else {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": None,
    }


def _verification_report(component_id):
    return {
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


def _license_scan_result(component_id):
    return {
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


def _inputs(component_id, with_files):
    return {
        "component_id": component_id,
        "generation_result": _generation_result(component_id, with_files),
        "verification_report": _verification_report(component_id) if with_files else None,
        "license_scan_result": _license_scan_result(component_id),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


@pytest.mark.parametrize("with_files", [True, False])
def test_written_manifest_is_valid_json_with_exact_schema_keys(tmp_path, with_files):
    component_id = "comp-foo"
    slug = "foo"
    repo_root = Path(tmp_path)

    result = provenance_writer.write_provenance(
        component_id, _inputs(component_id, with_files), repo_root
    )
    assert result is None

    paths = [
        repo_root / "gen" / slug / ".provenance.json",
        repo_root / "verification" / slug / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest not written at " + repr(str(path))
        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except ValueError as exc:  # pragma: no cover - failure path
            pytest.fail("manifest at " + repr(str(path)) + " is not valid JSON: " + repr(exc))
        assert isinstance(data, dict), "manifest top level must be a JSON object"
        keys = set(data.keys())
        missing = EXPECTED_KEYS - keys
        extra = keys - EXPECTED_KEYS
        assert not missing, "missing keys: " + repr(sorted(missing))
        assert not extra, "extra keys: " + repr(sorted(extra))
        assert keys == EXPECTED_KEYS