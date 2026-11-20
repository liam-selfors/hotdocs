# hotdocs-criterion: sha256:1a15084b48a55b1142f7e905e88aa00ff8321d23fe591ca95d893faff73f3c0c
import json
from pathlib import Path

import pytest

import provenance_writer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def clean_license_scan():
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.05,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def clean_secret_scan():
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


def generation_result(files):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
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


def passing_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


@pytest.mark.parametrize("with_candidate", [False, True])
def test_clean_scans_are_always_present_in_manifest(tmp_path, with_candidate):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    if with_candidate:
        gen = generation_result({"foo.py": "x = 1\n"})
        report = passing_report()
    else:
        gen = generation_result({})
        report = None

    license_scan = clean_license_scan()
    secret_scan = clean_secret_scan()

    inputs = {
        "component_id": "comp-foo",
        "generation_result": gen,
        "verification_report": report,
        "license_scan_result": license_scan,
        "secret_scan_result": secret_scan,
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {"license_scanner": "k-gram@1.0.0"},
    }

    provenance_writer.write_provenance("comp-foo", inputs, repo_root)

    paths = [
        repo_root / "gen" / "foo" / ".provenance.json",
        repo_root / "verification" / "foo" / ".provenance.json",
    ]
    for path in paths:
        assert path.is_file(), "manifest missing at " + str(path)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict)

        assert "license_scan" in manifest
        assert "secret_scan" in manifest
        assert manifest["license_scan"] is not None
        assert manifest["secret_scan"] is not None

        assert manifest["license_scan"] == license_scan
        assert manifest["secret_scan"] == secret_scan

        assert field(manifest["license_scan"], "blocked") is False
        assert field(manifest["license_scan"], "matches") == []
        assert field(manifest["secret_scan"], "flagged") is False
        assert field(manifest["secret_scan"], "matches") == []