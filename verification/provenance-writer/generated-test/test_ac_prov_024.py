# hotdocs-criterion: sha256:1c8639540e508e0fe393e57f52118cd4cef117c5663bbf2b46be5ec3d07ed8c6
import copy
import json
from pathlib import Path

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"

ASSETS = [
    {
        "kind": "fake",
        "path": "static/a.fake",
        "definition_sha256": "sha256:d1",
        "adapter_sha256": "sha256:a1",
        "versions": {"fakec": "2.0.0"},
        "lockfile_sha256": None,
    }
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(with_assets):
    report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "overall": "pass",
    }
    if with_assets:
        report["assets"] = copy.deepcopy(ASSETS)
    return report


def _inputs(files, verification_report):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": {
            "component_id": COMPONENT_ID,
            "spec_bundle_hash": "sha256:abc",
            "model": "claude-sonnet-5",
            "prompt_version": "v12",
            "cache_hit": False,
            "files": files,
            "model_call_error": None,
            "refused": None,
            "retry_feedback": None,
            "mode": "single",
            "transcript_sha256": None,
            "turns": 1,
            "tool_calls": 0,
            "isolation": None,
        },
        "verification_report": verification_report,
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
        assert p.is_file(), "manifest not written at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_assets_copied_verbatim_to_both_manifests(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _inputs({"foo.py": "x = 1\n"}, _verification_report(with_assets=True))

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifests = _read_manifests(repo_root)
    assert len(manifests) == 2
    for manifest in manifests:
        assert "assets" in manifest
        assert manifest["assets"] == ASSETS


def test_assets_empty_when_report_has_no_assets_key(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _inputs({"foo.py": "x = 1\n"}, _verification_report(with_assets=False))

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        assert "assets" in manifest
        assert manifest["assets"] == []


def test_assets_empty_when_report_is_null_and_files_empty(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _inputs({}, None)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _read_manifests(repo_root):
        assert "assets" in manifest
        assert manifest["assets"] == []