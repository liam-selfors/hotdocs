import json
from pathlib import Path

import pytest

import provenance_checker


def _write_provenance_manifest(repo_root: Path, spec_bundle_hash: str, gate_versions: dict) -> None:
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    }
    license_scan = {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    manifest = {
        "spec_bundle_hash": spec_bundle_hash,
        "gate_versions": gate_versions,
        "verification_report": verification_report,
        "license_scan": license_scan,
        "secret_scan": secret_scan,
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest))


def test_check_hit_returns_zero_and_prints_json_with_hit_true(tmp_path, capsys):
    _write_provenance_manifest(
        tmp_path, spec_bundle_hash="sha256:0a1b", gate_versions={"license_scanner": "1"}
    )

    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            '--gate-versions={"license_scanner": "1"}',
            f"--repo-root={tmp_path}",
            "--format=json",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["hit"] is True


def test_check_miss_returns_zero_and_prints_text_containing_miss(tmp_path, capsys):
    _write_provenance_manifest(
        tmp_path, spec_bundle_hash="sha256:0a1b", gate_versions={"license_scanner": "1"}
    )

    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash",
            "sha256:ffff",
            "--gate-versions",
            '{"license_scanner": "1"}',
            "--repo-root",
            str(tmp_path),
            "--format",
            "text",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "miss" in captured.out


def test_missing_spec_bundle_hash_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            '--gate-versions={"license_scanner": "1"}',
            f"--repo-root={tmp_path}",
            "--format=json",
        ]
    )
    assert code == 2


def test_spec_bundle_hash_without_sha256_prefix_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=0a1b",
            '--gate-versions={"license_scanner": "1"}',
            f"--repo-root={tmp_path}",
        ]
    )
    assert code == 2


def test_gate_versions_not_object_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions",
            "[1]",
            f"--repo-root={tmp_path}",
        ]
    )
    assert code == 2


def test_bogus_format_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            '--gate-versions={"license_scanner": "1"}',
            f"--repo-root={tmp_path}",
            "--format=bogus",
        ]
    )
    assert code == 2


def test_unknown_argument_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            '--gate-versions={"license_scanner": "1"}',
            f"--repo-root={tmp_path}",
            "--bogus-flag=1",
        ]
    )
    assert code == 2


def test_repo_root_as_last_argument_with_no_value_is_usage_error(tmp_path):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            '--gate-versions={"license_scanner": "1"}',
            "--repo-root",
        ]
    )
    assert code == 2