"""AC-PROV-003 (Covers: R-PROV-003).

Given reported versions from cache-manager, criterion-compiler, and
  license-scanner
When write_provenance runs
Then gate_versions contains exactly those three reported values, unmodified
"""

import copy
import dataclasses
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-prov-gate-fixture"
SLUG = "prov-gate-fixture"

CACHE_MANAGER_VERSION = "cache-manager@1.7.2"
CRITERION_COMPILER_VERSION = "criterion-compiler@3.0.1"
LICENSE_SCANNER_VERSION = "license_scanner@4.0.3+9f2c41ab07de"

REPORTED_GATE_VERSIONS = {
    "cache_manager": CACHE_MANAGER_VERSION,
    "criterion_compiler": CRITERION_COMPILER_VERSION,
    "license_scanner": LICENSE_SCANNER_VERSION,
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result():
    # A generation attempt that failed at the model call: no files, so
    # verification_report is legitimately null (no verifier version enters).
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "anthropic:claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection reset"},
        "refused": None,
        "retry_feedback": None,
    }


def _license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": LICENSE_SCANNER_VERSION,
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _secret_scan_result():
    # Precommit-scoped result, which MAY omit gate_version, so the only
    # reported gate versions in play are the three under test.
    return {
        "scope": "precommit",
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
        "verification_report": None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": copy.deepcopy(REPORTED_GATE_VERSIONS),
    }


def _build_inputs():
    fields = _inputs_fields()
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


def _read_manifest(path: Path):
    assert path.is_file(), f"expected manifest at {path}"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_gate_versions_are_exactly_the_reported_values_unmodified(tmp_path):
    repo_root = tmp_path
    (repo_root / "gen" / SLUG).mkdir(parents=True, exist_ok=True)
    (repo_root / "verification" / SLUG).mkdir(parents=True, exist_ok=True)

    inputs = _build_inputs()

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    gen_manifest = _read_manifest(repo_root / "gen" / SLUG / ".provenance.json")
    ver_manifest = _read_manifest(
        repo_root / "verification" / SLUG / ".provenance.json"
    )

    for manifest in (gen_manifest, ver_manifest):
        gate_versions = field(manifest, "gate_versions")
        assert isinstance(gate_versions, dict)
        # Exactly the three reported values: nothing invented, nothing dropped,
        # nothing rewritten.
        assert gate_versions == REPORTED_GATE_VERSIONS
        assert len(gate_versions) == 3
        assert sorted(gate_versions.values()) == sorted(
            [
                CACHE_MANAGER_VERSION,
                CRITERION_COMPILER_VERSION,
                LICENSE_SCANNER_VERSION,
            ]
        )

    # The writer must not have mutated the caller's reported data either.
    passed = field(inputs, "gate_versions")
    assert passed == REPORTED_GATE_VERSIONS