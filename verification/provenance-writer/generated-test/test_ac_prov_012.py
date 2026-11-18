# hotdocs-criterion: sha256:b4623324f46d86e943e1d2a5fcc757874ada81ecae9285c527502efff7ca307d
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _license_scan(component_id):
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


def _secret_scan():
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


def _inputs_a():
    component_id = "comp-alpha"
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v10",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "connection reset"},
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": None,
        "license_scan_result": _license_scan(component_id),
        "secret_scan_result": _secret_scan(),
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "k-gram@1.0.0"},
    }


def _inputs_b():
    component_id = "comp-beta-two"
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "b" * 64,
            "model": "claude-opus-5",
            "prompt_version": "v9",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": "sealed-component",
            "retry_feedback": ["R-BETA-003"],
        },
        "verification_report": None,
        "license_scan_result": _license_scan(component_id),
        "secret_scan_result": _secret_scan(),
        "provenance_hit": True,
        "attempts": 3,
        "gate_versions": {"compiler": "2.5.1", "license_scanner": "k-gram@9.9.9"},
    }


def _read(path):
    assert path.is_file(), "manifest missing at " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def test_pipeline_version_is_component_constant_independent_of_inputs(tmp_path):
    repo_root = Path(tmp_path)

    provenance_writer.write_provenance("comp-alpha", _inputs_a(), repo_root)
    provenance_writer.write_provenance("comp-beta-two", _inputs_b(), repo_root)

    manifest_a = _read(repo_root / "gen" / "alpha" / ".provenance.json")
    manifest_b = _read(repo_root / "gen" / "beta-two" / ".provenance.json")
    ver_a = _read(repo_root / "verification" / "alpha" / ".provenance.json")
    ver_b = _read(repo_root / "verification" / "beta-two" / ".provenance.json")

    constant = provenance_writer.PIPELINE_VERSION
    assert constant is not None

    pv_a = field(manifest_a, "pipeline_version")
    pv_b = field(manifest_b, "pipeline_version")

    assert pv_a == pv_b
    assert pv_a == constant
    assert pv_b == constant
    assert field(ver_a, "pipeline_version") == constant
    assert field(ver_b, "pipeline_version") == constant