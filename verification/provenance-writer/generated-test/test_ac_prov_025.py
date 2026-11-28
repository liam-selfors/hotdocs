# hotdocs-criterion: sha256:ff88fa3a1f687cd4c9d6b50752646ced10842f34ef8f6d98a74511b5f2c25c20
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def _base_inputs():
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": {},
            "model_call_error": None,
            "refused": "sealed-component",
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": None,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _read_manifests(repo_root):
    paths = [
        Path(repo_root) / "gen" / SLUG / ".provenance.json",
        Path(repo_root) / "verification" / SLUG / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), "missing manifest at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_spec_bundle_parts_copied_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _base_inputs()
    inputs["spec_bundle_parts"] = {"spec": "sha256:s", "dependency_code": "sha256:d"}

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        assert "spec_bundle_parts" in manifest
        assert manifest["spec_bundle_parts"] == {
            "spec": "sha256:s",
            "dependency_code": "sha256:d",
        }


def test_spec_bundle_parts_absent_is_null(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _base_inputs()
    assert "spec_bundle_parts" not in inputs

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        assert "spec_bundle_parts" in manifest
        assert manifest["spec_bundle_parts"] is None