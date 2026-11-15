"""AC-PROV-010 (Covers: R-PROV-010).

Given a completed write_provenance call
When both gen/<component>/.provenance.json and
  verification/<component>/.provenance.json are read back
Then their contents are byte-identical
"""

import dataclasses
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-provwidget"
SLUG = "provwidget"


def _generation_result_with_files():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {"provwidget.py": "def widget_value(x):\n    return x + 1\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }


def _generation_result_model_error():
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "model": "claude-sonnet-5",
        "prompt_version": "v10",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection reset"},
        "refused": None,
        "retry_feedback": ["R-PROVWIDGET-001"],
    }


def _verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {
                "id": "AC-PROVWIDGET-001",
                "covers": "R-PROVWIDGET-001",
                "kind": "compiled",
                "result": "pass",
            },
            {
                "id": "AC-PROVWIDGET-002",
                "covers": "R-PROVWIDGET-002",
                "kind": "llm-judge",
                "result": "skipped",
                "rationale": None,
            },
        ],
        "requirement_results": {
            "R-PROVWIDGET-001": "pass",
            "R-PROVWIDGET-002": "fail",
        },
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


def _make_inputs(generation_result, verification_report):
    fields = {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": _license_scan_result(),
        "secret_scan_result": _secret_scan_result(),
        "provenance_hit": False,
        "attempts": 2,
        "gate_versions": {
            "compiler": "1.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        },
    }
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**fields)
        except TypeError:
            pass
    return fields


@pytest.mark.parametrize(
    "scenario",
    ["verified-candidate", "never-reached-verification"],
)
def test_both_provenance_copies_are_byte_identical(tmp_path, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    if scenario == "verified-candidate":
        gen_result = _generation_result_with_files()
        report = _verification_report()
        # The generator would already have written the candidate here.
        gen_dir = repo_root / "gen" / SLUG
        gen_dir.mkdir(parents=True)
        for rel, content in gen_result["files"].items():
            (gen_dir / rel).write_text(content, encoding="utf-8")
    else:
        gen_result = _generation_result_model_error()
        report = None

    inputs = _make_inputs(gen_result, report)

    # Given a completed write_provenance call
    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    # When both copies are read back, by exact path
    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"

    assert gen_manifest.is_file(), f"missing {gen_manifest}"
    assert ver_manifest.is_file(), f"missing {ver_manifest}"

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()

    # Sanity: it is a real, non-empty JSON manifest, not two empty files.
    assert gen_bytes, "gen/ manifest is empty"
    parsed = json.loads(gen_bytes.decode("utf-8"))
    assert isinstance(parsed, dict)

    # Then their contents are byte-identical
    assert gen_bytes == ver_bytes


def test_rewrite_keeps_both_copies_byte_identical(tmp_path):
    """A second write must not let the two copies diverge either."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    first = _make_inputs(_generation_result_model_error(), None)
    provenance_writer.write_provenance(COMPONENT_ID, first, repo_root)

    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    gen_result = _generation_result_with_files()
    for rel, content in gen_result["files"].items():
        (gen_dir / rel).write_text(content, encoding="utf-8")

    second = _make_inputs(gen_result, _verification_report())
    provenance_writer.write_provenance(COMPONENT_ID, second, repo_root)

    gen_manifest = repo_root / "gen" / SLUG / ".provenance.json"
    ver_manifest = repo_root / "verification" / SLUG / ".provenance.json"

    gen_bytes = gen_manifest.read_bytes()
    ver_bytes = ver_manifest.read_bytes()

    assert gen_bytes
    assert isinstance(json.loads(gen_bytes.decode("utf-8")), dict)
    assert gen_bytes == ver_bytes