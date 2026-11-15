"""AC-PROV-010: both provenance manifest copies are byte-identical.

Given a completed write_provenance call
When both gen/<component>/.provenance.json and
  verification/<component>/.provenance.json are read back
Then their contents are byte-identical
"""

import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-provtarget"
SLUG = "provtarget"
SPEC_HASH = "sha256:" + "ab" * 32


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


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROVTARGET-001",
                "covers": "R-PROVTARGET-001",
                "kind": "compiled",
                "result": "pass",
            },
            {
                "id": "AC-PROVTARGET-002",
                "covers": "R-PROVTARGET-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
        ],
        "requirement_results": {
            "R-PROVTARGET-001": "pass",
            "R-PROVTARGET-002": "fail",
        },
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }


def _inputs_with_candidate():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": SPEC_HASH,
            "model": "claude-sonnet-5",
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {"provtarget.py": "def compute_value(x):\n    return x + 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-PROVTARGET-002"],
        },
        "verification_report": _verification_report(),
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }


def _inputs_without_candidate():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": SPEC_HASH,
            "model": "claude-sonnet-5",
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "connection reset"},
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": None,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0"},
    }


def _call_write(component_id, inputs, repo_root):
    """Call write_provenance with a plain dict; fall back to the module's
    ProvenanceInputs type if one exists and the dict form is rejected."""
    try:
        return provenance_writer.write_provenance(component_id, inputs, repo_root)
    except (TypeError, AttributeError):
        cls = getattr(provenance_writer, "ProvenanceInputs", None)
        if cls is None:
            raise
        return provenance_writer.write_provenance(component_id, cls(**inputs), repo_root)


@pytest.mark.parametrize(
    "make_inputs",
    [_inputs_with_candidate, _inputs_without_candidate],
    ids=["with-candidate", "no-candidate"],
)
def test_both_manifest_copies_are_byte_identical(tmp_path, make_inputs):
    repo_root = Path(tmp_path)

    _call_write(COMPONENT_ID, make_inputs(), repo_root)

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"

    assert gen_manifest.is_file(), f"missing manifest at {gen_manifest}"
    assert ver_manifest.is_file(), f"missing manifest at {ver_manifest}"

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()

    # Sanity: a real manifest was written, not an empty file.
    assert gen_bytes, "gen manifest is empty"
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(parsed, dict)

    # The criterion's Then clause: the two copies are byte-identical.
    assert gen_bytes == ver_bytes


def test_rewrite_keeps_both_copies_byte_identical(tmp_path):
    """A second completed write must leave the copies identical too,
    never one updated and the other stale."""
    repo_root = Path(tmp_path)

    _call_write(COMPONENT_ID, _inputs_without_candidate(), repo_root)
    _call_write(COMPONENT_ID, _inputs_with_candidate(), repo_root)

    gen_bytes = (repo_root / "gen" / SLUG / ".provenance.json").read_bytes()
    ver_bytes = (repo_root / "verification" / SLUG / ".provenance.json").read_bytes()

    assert gen_bytes
    assert gen_bytes == ver_bytes