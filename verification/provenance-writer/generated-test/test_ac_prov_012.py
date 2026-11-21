# hotdocs-criterion: sha256:1c9f42af923dc973c0b4741f00e786af41dab6d61196636798852862d61cf4b1
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _inputs_a():
    return {
        "component_id": "comp-alpha",
        "generation_result": {
            "component_id": "comp-alpha",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": {"category": "network", "message": "boom"},
            "refused": None,
            "retry_feedback": None,
        },
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _inputs_b():
    return {
        "component_id": "comp-beta-two",
        "generation_result": {
            "component_id": "comp-beta-two",
            "spec_bundle_hash": "sha256:" + "b" * 64,
            "model": "anthropic:claude-opus-5-5",
            "prompt_version": "v99",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": "sealed-component",
            "retry_feedback": ["R-BETA-001"],
            "mode": "single",
        },
        "verification_report": None,
        "license_scan_result": {"component_id": "comp-beta-two", "evaluated": False},
        "secret_scan_result": {"scope": "full", "flagged": False, "matches": []},
        "provenance_hit": True,
        "attempts": 3,
        "attempt_history": [
            {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
             "error_category": None, "failed_requirements": ["R-BETA-001"],
             "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "9.9.9", "license_scanner": "k-gram@2.0.0",
                          "pipeline": "should-not-be-used"},
    }


def _read_manifests(repo_root, slug):
    paths = [
        repo_root / "gen" / slug / ".provenance.json",
        repo_root / "verification" / slug / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), "manifest missing at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_pipeline_version_is_module_constant_across_calls(tmp_path):
    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    root_a.mkdir()
    root_b.mkdir()

    provenance_writer.write_provenance("comp-alpha", _inputs_a(), root_a)
    provenance_writer.write_provenance("comp-beta-two", _inputs_b(), root_b)

    manifests_a = _read_manifests(root_a, "alpha")
    manifests_b = _read_manifests(root_b, "beta-two")

    constant = provenance_writer.PIPELINE_VERSION

    versions = [field(m, "pipeline_version") for m in manifests_a + manifests_b]
    for v in versions:
        assert v == versions[0]
        assert v == constant

    assert field(manifests_a[0], "pipeline_version") == field(manifests_b[0], "pipeline_version")
    assert field(manifests_a[0], "pipeline_version") == constant
    assert field(manifests_b[0], "pipeline_version") == constant