# hotdocs-criterion: sha256:9cf56fb620c0e85c2a83f6fdace90826ec74181e72cae2665549c5a055b10db3
import copy
import json
from pathlib import Path

import provenance_writer


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

COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _generation_result(files):
    return {
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
    }


def _report(assets_present, assets=None):
    report = {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "overall": "pass",
    }
    if assets_present:
        report["assets"] = assets
    return report


def _inputs(generation_result, verification_report):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "license_scan_result": {},
        "secret_scan_result": {},
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {},
    }


def _manifests(repo_root):
    paths = [
        Path(repo_root) / "gen" / SLUG / ".provenance.json",
        Path(repo_root) / "verification" / SLUG / ".provenance.json",
    ]
    out = []
    for p in paths:
        assert p.is_file(), "manifest missing at " + str(p)
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def test_assets_copied_verbatim_into_both_manifests(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report(True, copy.deepcopy(ASSETS))
    inputs = _inputs(_generation_result({"foo.py": "x = 1\n"}), report)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    manifests = _manifests(repo_root)
    assert len(manifests) == 2
    for manifest in manifests:
        assert field(manifest, "assets") == ASSETS


def test_report_without_assets_key_gives_empty_assets(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    report = _report(False)
    assert "assets" not in report
    inputs = _inputs(_generation_result({"foo.py": "x = 1\n"}), report)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _manifests(repo_root):
        assert field(manifest, "assets") == []


def test_null_report_with_empty_files_gives_empty_assets(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = _inputs(_generation_result({}), None)

    provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)

    for manifest in _manifests(repo_root):
        assert field(manifest, "assets") == []