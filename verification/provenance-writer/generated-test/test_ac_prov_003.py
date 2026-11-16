"""AC-PROV-003 (Covers: R-PROV-003).

Given reported versions from cache-manager, criterion-compiler, and
  license-scanner
When write_provenance runs
Then gate_versions contains exactly those three reported values, unmodified
"""

import copy
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"
SLUG = "foo"
SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32

CACHE_MANAGER_VERSION = "cache-manager@1.7.3"
CRITERION_COMPILER_VERSION = "criterion-compiler@3.2.1"
LICENSE_SCANNER_VERSION = "license_scanner@4.0.0-no-reference-corpus"


def _reported_gate_versions():
    return {
        "cache_manager": CACHE_MANAGER_VERSION,
        "criterion_compiler": CRITERION_COMPILER_VERSION,
        "license_scanner": LICENSE_SCANNER_VERSION,
    }


def _generation_result():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"foo.py": "def bar(x):\n    return x\n"},
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
        "overall": "pass",
    }


def _license_scan_result():
    # The license scanner's own reported version, carried on its result too,
    # identical to the value reported in gate_versions.
    return {
        "component_id": COMPONENT_ID,
        "gate_version": LICENSE_SCANNER_VERSION,
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
    # A precommit-scope result, which MAY omit gate_version: the secret
    # scanner reports no version here, so only the three given gates did.
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


def _inputs():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": _generation_result(),
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": _reported_gate_versions(),
    }


def _read_manifest(path: Path):
    assert path.is_file(), f"expected manifest at {path}"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_ac_prov_003_gate_versions_are_exactly_the_reported_values(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    inputs = _inputs()
    expected = copy.deepcopy(_reported_gate_versions())

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    gen_manifest_path = repo_root / "gen" / SLUG / ".provenance.json"
    verification_manifest_path = (
        repo_root / "verification" / SLUG / ".provenance.json"
    )

    for manifest_path in (gen_manifest_path, verification_manifest_path):
        manifest = _read_manifest(manifest_path)
        gate_versions = field(manifest, "gate_versions")

        assert isinstance(gate_versions, dict), (
            f"gate_versions in {manifest_path} is not an object: {gate_versions!r}"
        )
        # Exactly those three reported values: nothing invented, nothing dropped.
        assert len(gate_versions) == 3, (
            f"gate_versions in {manifest_path} has extra or missing entries: "
            f"{gate_versions!r}"
        )
        assert sorted(gate_versions.values()) == sorted(expected.values()), (
            f"gate_versions in {manifest_path} values differ from reported: "
            f"{gate_versions!r} vs {expected!r}"
        )
        # Unmodified: each reported value appears verbatim under its gate.
        assert gate_versions == expected, (
            f"gate_versions in {manifest_path} was modified: "
            f"{gate_versions!r} vs {expected!r}"
        )

    # The handed-in data itself must not have been rewritten either.
    assert inputs["gate_versions"] == expected