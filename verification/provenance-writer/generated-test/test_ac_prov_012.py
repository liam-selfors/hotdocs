"""AC-PROV-012 (Covers: R-PROV-012).

Given two separate write_provenance calls, each with different ProvenanceInputs,
When each manifest is written,
Then both manifests' pipeline_version fields are identical, and equal this
component's own version constant (PIPELINE_VERSION).
"""

import dataclasses
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _make_inputs(data):
    """Build a ProvenanceInputs: the module's dataclass if it has one, else a dict."""
    cls = getattr(provenance_writer, "ProvenanceInputs", None)
    if cls is not None and dataclasses.is_dataclass(cls):
        try:
            return cls(**data)
        except TypeError:
            pass
    return dict(data)


def _license_scan(component_id, score):
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
    } if score is None else {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": score,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": True,
    }


def _secret_scan(cache_hit):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": cache_hit,
    }


def _inputs_a():
    component_id = "comp-alpha-widget"
    return component_id, {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {"alpha_widget.py": "def compute_alpha(x):\n    return x\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": {
            "component_id": component_id,
            "criteria": [
                {"id": "AC-ALPHA-001", "covers": "R-ALPHA-001",
                 "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-ALPHA-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "overall": "pass",
        },
        "license_scan_result": _license_scan(component_id, 0.1),
        "secret_scan_result": _secret_scan(False),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _inputs_b():
    component_id = "comp-beta-gadget"
    return component_id, {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "b" * 64,
            "model": "ollama:llama3.1:8b",
            "prompt_version": "v9",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "connection reset"},
            "refused": None,
            "retry_feedback": ["R-BETA-002", "R-BETA-007"],
        },
        "verification_report": None,
        "license_scan_result": _license_scan(component_id, None),
        "secret_scan_result": _secret_scan(True),
        "provenance_hit": True,
        "attempts": 3,
        "gate_versions": {
            "compiler": "9.9.9",
            "license_scanner": "k-gram@7.0.0",
            "pipeline": "not-the-pipeline-version",
        },
    }


def _read_manifests(repo_root, component_id):
    slug = component_id[len("comp-"):]
    paths = [
        repo_root / "gen" / slug / ".provenance.json",
        repo_root / "verification" / slug / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), f"expected manifest at {p}"
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_pipeline_version_is_component_constant_independent_of_inputs(tmp_path):
    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    root_a.mkdir()
    root_b.mkdir()

    cid_a, data_a = _inputs_a()
    cid_b, data_b = _inputs_b()

    provenance_writer.write_provenance(cid_a, _make_inputs(data_a), Path(root_a))
    provenance_writer.write_provenance(cid_b, _make_inputs(data_b), Path(root_b))

    manifests_a = _read_manifests(root_a, cid_a)
    manifests_b = _read_manifests(root_b, cid_b)

    versions = [field(m, "pipeline_version") for m in manifests_a + manifests_b]

    # Both manifests' pipeline_version fields are identical...
    assert len(set(json.dumps(v, sort_keys=True) for v in versions)) == 1, versions

    # ...and equal this component's own version constant.
    constant = provenance_writer.PIPELINE_VERSION
    for v in versions:
        assert v == constant

    # Never sourced from the inputs (e.g. a gate_versions entry).
    assert versions[0] != "not-the-pipeline-version"