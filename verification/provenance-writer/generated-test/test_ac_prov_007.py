# hotdocs-criterion: sha256:3ec0ac36326cbd14bb23d230b01914a2c3f2e0bc371093872ef17d02d114e369
import json
from pathlib import Path

import pytest

import provenance_writer


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def clean_license_scan_result():
    return {
        "component_id": COMPONENT_ID,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def clean_secret_scan_result():
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
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:" + "a" * 64,
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


def verification_report():
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "b" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }


def build_inputs(files, report):
    return {
        "component_id": COMPONENT_ID,
        "generation_result": generation_result(files),
        "verification_report": report,
        "license_scan_result": clean_license_scan_result(),
        "secret_scan_result": clean_secret_scan_result(),
        "provenance_hit": False,
        "attempts": 1,
        "attempt_history": [],
        "gate_versions": {"compiler": "1.0.0", "license_scanner": "license_scanner@4.0.3+9f2c41ab07de"},
        "spec_bundle_parts": None,
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


@pytest.mark.parametrize(
    "files,report",
    [
        ({}, None),
        ({"foo.py": "x = 1\n"}, "report"),
    ],
    ids=["no-candidate", "verified-candidate"],
)
def test_clean_scans_are_still_recorded(tmp_path, files, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inputs = build_inputs(files, verification_report() if report else None)

    result = provenance_writer.write_provenance(COMPONENT_ID, inputs, repo_root)
    assert result is None

    for manifest in read_manifests(repo_root):
        assert "license_scan" in manifest
        assert "secret_scan" in manifest
        license_scan = manifest["license_scan"]
        secret_scan = manifest["secret_scan"]
        assert license_scan is not None
        assert secret_scan is not None
        assert license_scan == clean_license_scan_result()
        assert secret_scan == clean_secret_scan_result()
        assert field(license_scan, "blocked") is False
        assert field(license_scan, "matches") == []
        assert field(secret_scan, "flagged") is False
        assert field(secret_scan, "matches") == []