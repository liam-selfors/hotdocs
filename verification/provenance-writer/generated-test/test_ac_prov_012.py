"""AC-PROV-012 (Covers: R-PROV-012).

Given two separate write_provenance calls, each with different
ProvenanceInputs, when each manifest is written, then both manifests'
pipeline_version fields are identical, and equal this component's own
version constant (PIPELINE_VERSION).
"""

import dataclasses
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _secret_scan_result(flagged=False):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": flagged,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _make_inputs(data):
    """Build ProvenanceInputs: the module's own type if it exposes one, else a dict."""
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            pass
    return data


def _inputs_one():
    component_id = "comp-alpha"
    return _make_inputs(
        {
            "component_id": component_id,
            "generation_result": {
                "component_id": component_id,
                "spec_bundle_hash": "sha256:" + "1" * 64,
                "model": "claude-sonnet-5",
                "prompt_version": "v10",
                "cache_hit": False,
                "files": {},
                "model_call_error": {"category": "network", "message": "connection reset"},
                "refused": None,
                "retry_feedback": None,
            },
            "verification_report": None,
            "license_scan_result": _license_scan_result(component_id),
            "secret_scan_result": _secret_scan_result(flagged=False),
            "provenance_hit": False,
            "attempts": 1,
            "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
        }
    )


def _inputs_two():
    component_id = "comp-beta"
    return _make_inputs(
        {
            "component_id": component_id,
            "generation_result": {
                "component_id": component_id,
                "spec_bundle_hash": "sha256:" + "2" * 64,
                "model": "claude-opus-5",
                "prompt_version": "v9",
                "cache_hit": False,
                "files": {},
                "model_call_error": None,
                "refused": "sealed-component",
                "retry_feedback": ["R-BETA-003"],
            },
            "verification_report": None,
            "license_scan_result": _license_scan_result(component_id),
            "secret_scan_result": _secret_scan_result(flagged=False),
            "provenance_hit": True,
            "attempts": 3,
            "gate_versions": {"compiler": "9.9.9", "license_scanner": "k-gram@7.0.0"},
        }
    )


def _read_manifests(repo_root, slug):
    paths = [
        Path(repo_root) / "gen" / slug / ".provenance.json",
        Path(repo_root) / "verification" / slug / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), f"expected manifest at {p}"
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_pipeline_version_is_identical_across_calls_and_equals_constant(tmp_path):
    assert hasattr(provenance_writer, "PIPELINE_VERSION"), (
        "provenance_writer must expose its own PIPELINE_VERSION constant"
    )
    expected = provenance_writer.PIPELINE_VERSION

    repo_one = tmp_path / "repo_one"
    repo_two = tmp_path / "repo_two"
    repo_one.mkdir()
    repo_two.mkdir()

    provenance_writer.write_provenance("comp-alpha", _inputs_one(), repo_one)
    provenance_writer.write_provenance("comp-beta", _inputs_two(), repo_two)

    manifests_one = _read_manifests(repo_one, "alpha")
    manifests_two = _read_manifests(repo_two, "beta")

    versions = []
    for manifest in manifests_one + manifests_two:
        assert "pipeline_version" in manifest, "manifest lacks pipeline_version"
        versions.append(manifest["pipeline_version"])

    # Both manifests' pipeline_version fields are identical...
    assert len(set(json.dumps(v, sort_keys=True) for v in versions)) == 1, versions
    # ...and equal this component's own version constant.
    for v in versions:
        assert v == expected

    # Not computed from inputs: it matches neither call's input-derived values.
    for v in versions:
        assert v not in ("v10", "v9", "1.0.0", "9.9.9", "k-gram@1.0.0", "k-gram@7.0.0") or v == expected