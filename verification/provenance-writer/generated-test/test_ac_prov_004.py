# hotdocs-criterion: sha256:dc5b8ef369782519a3db5ac1a174dd3e92460afb3710d82315bfbe26633607c4
import json
from pathlib import Path

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _minimal_inputs(component_id):
    # Every gate's own result says "no hit", so a provenance_hit of true in
    # the manifest can only come from the caller's own ProvenanceInputs field.
    return {
        "component_id": component_id,
        "generation_result": {
            "component_id": component_id,
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": {"cache_hit": False},
        "secret_scan_result": {"cache_hit": False},
        "provenance_hit": True,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _manifest_paths(repo_root, slug):
    return [
        repo_root / "gen" / slug / ".provenance.json",
        repo_root / "verification" / slug / ".provenance.json",
    ]


def test_ac_prov_004_provenance_hit_true_is_copied_from_inputs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-foo"
    inputs = _minimal_inputs(component_id)

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    for path in _manifest_paths(repo_root, "foo"):
        assert path.is_file(), "manifest not written at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "provenance_hit") is True


def test_ac_prov_004_provenance_hit_true_with_verification_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    component_id = "comp-bar"
    inputs = _minimal_inputs(component_id)
    inputs["generation_result"]["files"] = {"bar.py": "x = 1\n"}
    inputs["verification_report"] = {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }

    provenance_writer.write_provenance(component_id, inputs, repo_root)

    for path in _manifest_paths(repo_root, "bar"):
        assert path.is_file(), "manifest not written at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert field(manifest, "provenance_hit") is True