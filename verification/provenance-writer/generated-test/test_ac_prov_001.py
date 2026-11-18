# hotdocs-criterion: sha256:6a4c396bd75ca10fd4124e68a3ccf71d8601e5a91e80de0ffb9a2b4af31b44ea
"""AC-PROV-001: the written manifest's top-level keys exactly match
SPEC_GUIDELINES.md section 7's field list, with no extra keys and none missing."""

import dataclasses
import json
from pathlib import Path

import pytest

import provenance_writer


# SPEC_GUIDELINES.md section 7's provenance manifest field list.
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

COMPONENT_ID = "comp-foo"
SLUG = "foo"
SPEC_HASH = "sha256:" + "ab" * 32


def _generation_result(with_files):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_HASH,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def foo():\n    return 1\n"} if with_files else {},
        "model_call_error": None if with_files else {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": ["R-FOO-003"] if with_files else None,
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.92,
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


def _inputs_dict(with_files):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(with_files),
        "verification_report": _verification_report() if with_files else None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _build_inputs(with_files):
    data = _inputs_dict(with_files)
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            return data
    return data


def _read_manifest(path):
    assert path.is_file(), "manifest not written at " + str(path)
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert isinstance(manifest, dict), "manifest is not a JSON object"
    return manifest


@pytest.mark.parametrize("with_files", [True, False], ids=["verified", "never-verified"])
def test_manifest_top_level_keys_exactly_match_schema(tmp_path, with_files):
    repo_root = Path(tmp_path)
    inputs = _build_inputs(with_files)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for location in (
        repo_root / "gen" / SLUG / ".provenance.json",
        repo_root / "verification" / SLUG / ".provenance.json",
    ):
        manifest = _read_manifest(location)
        keys = set(manifest.keys())
        extra = keys - EXPECTED_KEYS
        missing = EXPECTED_KEYS - keys
        assert not extra, "extra keys in " + str(location) + ": " + repr(sorted(extra))
        assert not missing, "missing keys in " + str(location) + ": " + repr(sorted(missing))
        assert keys == EXPECTED_KEYS