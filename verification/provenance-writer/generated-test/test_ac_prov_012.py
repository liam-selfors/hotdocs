# hotdocs-criterion: sha256:8a2120515fbd81d372ed490a2436abb4f0eb017bf841c3bc47b2128aa3f121e6
import json
from pathlib import Path

import provenance_writer


def _read_manifests(repo_root, slug):
    gen_path = Path(repo_root) / "gen" / slug / ".provenance.json"
    ver_path = Path(repo_root) / "verification" / slug / ".provenance.json"
    assert gen_path.is_file(), "missing manifest at " + str(gen_path)
    assert ver_path.is_file(), "missing manifest at " + str(ver_path)
    return (
        json.loads(gen_path.read_text(encoding="utf-8")),
        json.loads(ver_path.read_text(encoding="utf-8")),
    )


def _first_inputs():
    return {
        "component_id": "comp-alpha",
        "generation_result": {"files": {}},
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "gate_versions": {},
    }


def _second_inputs():
    return {
        "component_id": "comp-beta-two",
        "generation_result": {
            "component_id": "comp-beta-two",
            "spec_bundle_hash": "sha256:" + "a" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v99",
            "cache_hit": False,
            "files": {"beta_two.py": "x = 1\n"},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": ["R-BETA-001"],
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
            "pipeline_version": "bogus-from-generation-result",
        },
        "verification_report": {
            "component_id": "comp-beta-two",
            "criteria": [
                {"id": "AC-BETA-001", "covers": "R-BETA-001",
                 "kind": "compiled", "result": "pass"},
            ],
            "requirement_results": {"R-BETA-001": "pass"},
            "interface_drift": False,
            "mutation_score": 0.9,
            "mutation_error": None,
            "assets": [],
            "overall": "pass",
            "pipeline_version": "bogus-from-report",
        },
        "license_scan_result": {"component_id": "comp-beta-two", "blocked": False},
        "secret_scan_result": {"scope": "full", "flagged": False, "matches": []},
        "provenance_hit": True,
        "attempts": 3,
        "attempt_history": [
            {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
             "error_category": None, "failed_requirements": ["R-BETA-001"],
             "transcript_sha256": None},
        ],
        "gate_versions": {"compiler": "9.9.9", "pipeline_version": "bogus-gate"},
        "pipeline_version": "bogus-top-level",
    }


def test_pipeline_version_is_module_constant_across_calls(tmp_path):
    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    root_a.mkdir()
    root_b.mkdir()

    provenance_writer.write_provenance("comp-alpha", _first_inputs(), root_a)
    provenance_writer.write_provenance("comp-beta-two", _second_inputs(), root_b)

    a_gen, a_ver = _read_manifests(root_a, "alpha")
    b_gen, b_ver = _read_manifests(root_b, "beta-two")

    constant = provenance_writer.PIPELINE_VERSION

    versions = [m["pipeline_version"] for m in (a_gen, a_ver, b_gen, b_ver)]
    assert versions[0] == versions[2], versions
    for v in versions:
        assert v == constant, (v, constant)

    for bogus in ("bogus-from-generation-result", "bogus-from-report",
                  "bogus-gate", "bogus-top-level"):
        assert constant != bogus