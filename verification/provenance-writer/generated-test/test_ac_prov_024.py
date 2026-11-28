# hotdocs-criterion: sha256:232f091ea8b831a22cfcbb137fcc660d57fa36ec8bcab1af5363aabba347680e
import json
from pathlib import Path

import pytest

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

DRIVERS = [
    {
        "name": "fake",
        "definition_sha256": None,
        "adapter_sha256": "sha256:a2",
        "versions": {"fakedrv": "2.0"},
        "lockfile_sha256": None,
    }
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def base_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "overall": "pass",
    }


def make_inputs(verification_report, files):
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


def read_manifests(repo_root):
    paths = [
        Path(repo_root) / "gen" / SLUG / ".provenance.json",
        Path(repo_root) / "verification" / SLUG / ".provenance.json",
    ]
    manifests = []
    for p in paths:
        assert p.is_file(), "manifest missing at " + str(p)
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    return manifests


def test_assets_and_drivers_copied_verbatim(tmp_path):
    report = base_report()
    report["assets"] = json.loads(json.dumps(ASSETS))
    report["drivers"] = json.loads(json.dumps(DRIVERS))
    inputs = make_inputs(report, {"foo.py": "x = 1\n"})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    manifests = read_manifests(tmp_path)
    assert len(manifests) == 2
    for manifest in manifests:
        assert field(manifest, "assets") == ASSETS
        assert field(manifest, "drivers") == DRIVERS


def test_report_without_assets_or_drivers_keys_gives_empty_lists(tmp_path):
    report = base_report()
    assert "assets" not in report and "drivers" not in report
    inputs = make_inputs(report, {"foo.py": "x = 1\n"})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in read_manifests(tmp_path):
        assert field(manifest, "assets") == []
        assert field(manifest, "drivers") == []


def test_report_with_null_assets_and_drivers_gives_empty_lists(tmp_path):
    report = base_report()
    report["assets"] = None
    report["drivers"] = None
    inputs = make_inputs(report, {"foo.py": "x = 1\n"})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in read_manifests(tmp_path):
        assert field(manifest, "assets") == []
        assert field(manifest, "drivers") == []


def test_null_report_with_empty_files_gives_empty_lists(tmp_path):
    inputs = make_inputs(None, {})

    provenance_writer.write_provenance(COMPONENT_ID, inputs, tmp_path)

    for manifest in read_manifests(tmp_path):
        assert field(manifest, "assets") == []
        assert field(manifest, "drivers") == []